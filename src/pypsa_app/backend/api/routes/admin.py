"""Admin routes for user, network, and backend management"""

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.api.deps import (
    get_backend,
    get_db,
    get_user,
    require_permission,
)
from pypsa_app.backend.api.pagination import (
    FilteredListParams,
    apply_pagination,
    list_meta,
)
from pypsa_app.backend.api.utils.network import delete_network
from pypsa_app.backend.filters import (
    FieldMap,
    FieldSpec,
    apply_filter_to_query,
    enum_coercer,
    name_to_id,
)
from pypsa_app.backend.models import (
    ApiKey,
    Network,
    Permission,
    Run,
    SnakedispatchBackend,
    User,
    UserRole,
    Visibility,
)
from pypsa_app.backend.permissions import get_role_permissions
from pypsa_app.backend.schemas.api_key import ApiKeyResponse
from pypsa_app.backend.schemas.auth import (
    UserCreate,
    UserListResponse,
    UserResponse,
    UserRoleUpdate,
)
from pypsa_app.backend.schemas.backend import (
    BackendAssign,
    BackendResponse,
    UserBackendAssign,
)
from pypsa_app.backend.schemas.common import MessageResponse
from pypsa_app.backend.schemas.network import (
    NetworkAdminUpdate,
    NetworkListResponse,
    NetworkResponse,
)
from pypsa_app.backend.schemas.run import (
    RunAdminUpdate,
    RunListResponse,
    RunResponse,
    RunSummary,
)
from pypsa_app.backend.schemas.stats import UserStatsResponse
from pypsa_app.backend.services.backend_registry import backend_registry
from pypsa_app.backend.services.email import send_account_approved_email

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/permissions")
def get_permissions(
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> dict:
    """Get all available permissions and role mappings"""
    return {
        "permissions": [p.value for p in Permission],
        "role_permissions": {
            role.value: [p.value for p in perms]
            for role, perms in get_role_permissions().items()
        },
    }


_USER_FIELD_MAP: FieldMap = {
    "role": FieldSpec(User.role, enum_coercer(UserRole)),
}


@router.get("/users", response_model=UserListResponse)
def list_users(
    filters: FilteredListParams = Depends(),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> UserListResponse:
    """List all users"""
    query = select(User)

    query = apply_filter_to_query(
        query,
        filters.filter_q,
        _USER_FIELD_MAP,
        text_fields=(User.username, User.email),
    )

    users_query, total = apply_pagination(
        query,
        User,
        filters,
        session=db,
        allowed_sort_fields={"created_at", "username", "email", "last_login", "role"},
    )
    users = db.scalars(users_query).all()

    return UserListResponse(
        data=users,
        meta=list_meta(total, filters, len(users)),
    )


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user_detail(
    user: User = Depends(get_user),
    _admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> User:
    """Get a single user by ID."""
    return user


@router.get("/users/{user_id}/stats", response_model=UserStatsResponse)
def get_user_stats(
    user: User = Depends(get_user),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> UserStatsResponse:
    """Aggregated activity stats for a single user."""
    user_id = user.id

    net_row = db.execute(
        select(
            func.count(Network.id),
            func.coalesce(func.sum(Network.file_size), 0),
            func.max(Network.created_at),
        ).where(Network.user_id == user_id)
    ).one()
    networks_count, total_storage_bytes, max_network_created = net_row

    run_rows = db.execute(
        select(Run.status, func.count())
        .where(Run.user_id == user_id)
        .group_by(Run.status)
    ).all()
    runs_by_status = {str(status): count for status, count in run_rows}
    runs_total = sum(runs_by_status.values())

    backend_rows = db.execute(
        select(SnakedispatchBackend.name, func.count())
        .join(Run, Run.backend_id == SnakedispatchBackend.id)
        .where(Run.user_id == user_id)
        .group_by(SnakedispatchBackend.name)
    ).all()
    runs_by_backend = dict(backend_rows)

    max_run_created = db.scalar(
        select(func.max(Run.created_at)).where(Run.user_id == user_id)
    )

    max_api_key_used = db.scalar(
        select(func.max(ApiKey.last_used_at)).where(ApiKey.user_id == user_id)
    )

    candidates = [
        user.last_login, max_network_created, max_run_created, max_api_key_used,
    ]
    last_activity = max((c for c in candidates if c is not None), default=None)

    return UserStatsResponse(
        networks_count=networks_count,
        runs_total=runs_total,
        runs_by_status=runs_by_status,
        runs_by_backend=runs_by_backend,
        total_storage_bytes=int(total_storage_bytes),
        last_activity=last_activity,
    )


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> User:
    """Create a user (currently only bot role is supported)."""
    if body.role != UserRole.BOT:
        raise HTTPException(400, "Only bot users can be created via API")

    existing = db.scalars(select(User).where(User.username == body.username)).first()
    if existing:
        raise HTTPException(409, "Username already taken")

    user = User(username=body.username, role=body.role, avatar_url=body.avatar_url)
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(
        "User created: %s (role=%s) by %s",
        user.username,
        body.role,
        admin.username,
    )
    return user


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    role_update: UserRoleUpdate,
    user: User = Depends(get_user),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> User:
    """Update user role"""
    if user.id == admin.id and role_update.role != UserRole.ADMIN:
        raise HTTPException(400, "Cannot remove your own admin role")

    old_role = user.role
    user.role = role_update.role
    db.commit()
    db.refresh(user)

    logger.info(
        "User role updated: %s (%s -> %s) by %s",
        user.username,
        old_role,
        user.role,
        admin.username,
    )

    return user


@router.post("/users/{user_id}/approve", response_model=UserResponse)
def approve_user(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_user),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> User:
    """Approve a pending user"""
    if user.role != UserRole.PENDING:
        raise HTTPException(
            400,
            f"User is not pending approval (current role: {user.role.value})",
        )

    user.role = UserRole.USER
    db.commit()
    db.refresh(user)

    logger.info("User approved: %s by %s", user.username, admin.username)

    if user.email:
        background_tasks.add_task(
            send_account_approved_email,
            user.username,
            user.email,
        )

    return user


@router.delete("/users/{user_id}", response_model=MessageResponse)
def delete_user(
    user: User = Depends(get_user),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> dict:
    """Delete a user"""
    if user.id == admin.id:
        raise HTTPException(400, "Cannot delete yourself")

    username = user.username
    db.delete(user)
    db.commit()

    logger.info("User deleted: %s by %s", username, admin.username)

    return {"message": f"User {username} deleted successfully"}


def _build_admin_network_field_map(db: Session) -> FieldMap:
    return {
        "visibility": FieldSpec(Network.visibility, enum_coercer(Visibility)),
        "owner": FieldSpec(Network.user_id, name_to_id(db, User, "username", "user")),
    }


@router.get("/networks", response_model=NetworkListResponse)
def list_all_networks(
    filters: FilteredListParams = Depends(),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.NETWORKS_MANAGE_ALL)),
) -> NetworkListResponse:
    """List ALL networks (admin only) - bypasses normal visibility rules"""
    query = select(Network).options(joinedload(Network.owner))

    query = apply_filter_to_query(
        query,
        filters.filter_q,
        _build_admin_network_field_map(db),
        text_fields=(Network.filename, Network.name),
    )

    networks_query, total = apply_pagination(
        query,
        Network,
        filters,
        session=db,
        allowed_sort_fields={"created_at", "name", "filename", "file_size"},
    )
    networks = db.scalars(networks_query).all()

    return NetworkListResponse(
        data=networks,
        meta=list_meta(total, filters, len(networks)),
    )


@router.patch("/networks/{network_id}", response_model=NetworkResponse)
def update_network_admin(
    network_id: UUID,
    body: NetworkAdminUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.NETWORKS_MANAGE_ALL)),
) -> Network:
    """Update network properties (admin only) - can change owner, visibility, name"""
    network = db.scalars(
        select(Network)
        .options(joinedload(Network.owner))
        .where(Network.id == network_id)
    ).first()

    if not network:
        raise HTTPException(404, "Network not found")

    # Track changes for logging
    changes = []

    # Update user_id (owner)
    if body.user_id is not None:
        old_owner = network.owner.username
        new_owner = db.get(User, body.user_id)
        if not new_owner:
            raise HTTPException(400, "Specified owner does not exist")
        network.user_id = body.user_id
        changes.append(f"owner: {old_owner} -> {new_owner.username}")
    elif "user_id" in body.model_fields_set:
        raise HTTPException(400, "Cannot set owner to null")

    # Update visibility
    if body.visibility is not None:
        old_vis = network.visibility.value
        network.visibility = body.visibility
        changes.append(f"visibility: {old_vis} -> {body.visibility.value}")

    # Update name
    if body.name is not None:
        old_name = network.name or "(none)"
        network.name = body.name
        changes.append(f"name: {old_name} -> {body.name}")

    if changes:
        db.commit()
        db.refresh(network)
        logger.info(
            "Network updated by admin: %s - %s by %s",
            network.filename,
            ", ".join(changes),
            admin.username,
        )

    return network


@router.delete("/networks/{network_id}", response_model=MessageResponse)
def delete_network_admin(
    network_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.NETWORKS_MANAGE_ALL)),
) -> dict:
    """Delete any network (admin only)"""
    network = db.get(Network, network_id)
    if not network:
        raise HTTPException(404, "Network not found")

    message = delete_network(network, db)
    logger.info("Network deleted by admin: %s by %s", network.filename, admin.username)
    return {"message": message}


# --- Run management ---


def _build_admin_run_field_map(db: Session) -> FieldMap:
    return {
        "visibility": FieldSpec(Run.visibility, enum_coercer(Visibility)),
        "owner": FieldSpec(Run.user_id, name_to_id(db, User, "username", "user")),
    }


@router.get("/runs", response_model=RunListResponse)
def list_all_runs(
    filters: FilteredListParams = Depends(),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.RUNS_MANAGE_ALL)),
) -> RunListResponse:
    """List ALL runs (admin only) - bypasses normal visibility rules"""
    query = select(Run).options(joinedload(Run.owner), joinedload(Run.backend))

    query = apply_filter_to_query(
        query,
        filters.filter_q,
        _build_admin_run_field_map(db),
        text_fields=(Run.workflow, Run.configfile),
    )

    runs_query, total = apply_pagination(
        query,
        Run,
        filters,
        session=db,
        allowed_sort_fields={"created_at", "status", "workflow"},
    )
    runs = db.scalars(runs_query).all()

    return RunListResponse(
        data=[RunSummary.model_validate(r) for r in runs],
        meta=list_meta(total, filters, len(runs)),
    )


@router.patch("/runs/{run_id}", response_model=RunResponse)
def update_run_admin(
    run_id: UUID,
    body: RunAdminUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.RUNS_MANAGE_ALL)),
) -> RunResponse:
    """Update run properties (admin only) - can change owner, visibility"""
    run = (
        db.scalars(
            select(Run)
            .options(
                joinedload(Run.owner),
                joinedload(Run.backend),
                joinedload(Run.networks),
            )
            .where(Run.job_id == run_id)
        )
        .unique()
        .first()
    )
    if not run:
        raise HTTPException(404, "Run not found")

    changes = []

    if body.user_id is not None:
        old_owner = run.owner.username
        new_owner = db.get(User, body.user_id)
        if not new_owner:
            raise HTTPException(400, "Specified owner does not exist")
        run.user_id = body.user_id
        changes.append(f"owner: {old_owner} -> {new_owner.username}")
    elif "user_id" in body.model_fields_set:
        raise HTTPException(400, "Cannot set owner to null")

    if body.visibility is not None:
        old_vis = run.visibility.value
        run.visibility = body.visibility
        changes.append(f"visibility: {old_vis} -> {body.visibility.value}")

    if changes:
        db.commit()
        db.refresh(run)
        logger.info(
            "Run updated by admin: %s - %s by %s",
            run.job_id,
            ", ".join(changes),
            admin.username,
        )

    return RunResponse.model_validate(run)


@router.delete("/runs/{run_id}", response_model=MessageResponse)
def delete_run_admin(
    run_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.RUNS_MANAGE_ALL)),
) -> dict:
    """Delete any run (admin only)"""
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    # Clean up remote job on the execution backend
    client = backend_registry.get_client(run.backend_id)
    if client:
        try:
            client.delete_job(str(run_id))
        except Exception:
            logger.warning("Remote cleanup failed for run %s", run_id, exc_info=True)

    db.delete(run)
    db.commit()
    logger.info("Run deleted by admin: %s by %s", run_id, admin.username)
    return {"message": "Run removed"}


# --- Backend management ---


@router.get("/backends", response_model=list[BackendResponse])
def list_backends(
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> list[SnakedispatchBackend]:
    """List all registered Snakedispatch backends."""
    return db.scalars(
        select(SnakedispatchBackend).order_by(SnakedispatchBackend.name)
    ).all()


@router.get("/backends/{backend_id}", response_model=BackendResponse)
def get_backend_detail(
    backend: SnakedispatchBackend = Depends(get_backend),
) -> SnakedispatchBackend:
    """Get a single backend by ID."""
    return backend


@router.get("/backends/{backend_id}/users", response_model=list[UserResponse])
def list_backend_users(
    backend: SnakedispatchBackend = Depends(get_backend),
) -> list[User]:
    """List users assigned to a backend."""
    return backend.users


@router.post("/backends/{backend_id}/users", response_model=MessageResponse)
def assign_user_to_backend(
    body: UserBackendAssign,
    db: Session = Depends(get_db),
    backend: SnakedispatchBackend = Depends(get_backend),
) -> dict:
    """Assign a user to a backend."""
    user = db.get(User, body.user_id)
    if not user:
        raise HTTPException(404, "User not found")

    if user in backend.users:
        raise HTTPException(409, "User already assigned to this backend")

    backend.users.append(user)
    db.commit()
    logger.info(
        "User %s assigned to backend %s",
        user.username,
        backend.name,
    )
    return {"message": f"User {user.username} assigned to backend {backend.name}"}


@router.delete("/backends/{backend_id}/users/{user_id}", response_model=MessageResponse)
def unassign_user_from_backend(
    user: User = Depends(get_user),
    backend: SnakedispatchBackend = Depends(get_backend),
    db: Session = Depends(get_db),
) -> dict:
    """Remove a user from a backend."""
    if user not in backend.users:
        raise HTTPException(404, "User is not assigned to this backend")

    backend.users.remove(user)
    db.commit()
    logger.info(
        "User %s unassigned from backend %s",
        user.username,
        backend.name,
    )
    return {"message": f"User {user.username} removed from backend {backend.name}"}


# --- User-side many-to-many mirrors and user-scoped api-keys ---


@router.get("/users/{user_id}/backends", response_model=list[BackendResponse])
def list_user_backends(
    user: User = Depends(get_user),
    _admin: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> list[SnakedispatchBackend]:
    """List backends assigned to a user."""
    return user.backends


@router.post("/users/{user_id}/backends", response_model=MessageResponse)
def assign_backend_to_user(
    body: BackendAssign,
    user: User = Depends(get_user),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> dict:
    """Assign a backend to a user (mirror of POST /backends/{id}/users)."""
    backend = db.get(SnakedispatchBackend, body.backend_id)
    if not backend:
        raise HTTPException(404, "Backend not found")

    if backend in user.backends:
        raise HTTPException(409, "Backend already assigned to this user")

    user.backends.append(backend)
    db.commit()
    logger.info("Backend %s assigned to user %s", backend.name, user.username)
    return {"message": f"Backend {backend.name} assigned to user {user.username}"}


@router.delete("/users/{user_id}/backends/{backend_id}", response_model=MessageResponse)
def unassign_backend_from_user(
    backend_id: UUID,
    user: User = Depends(get_user),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> dict:
    """Remove a backend from a user.

    Mirror of DELETE /backends/{id}/users/{user_id}.
    """
    backend = db.get(SnakedispatchBackend, backend_id)
    if not backend:
        raise HTTPException(404, "Backend not found")

    if backend not in user.backends:
        raise HTTPException(404, "Backend is not assigned to this user")

    user.backends.remove(backend)
    db.commit()
    logger.info("Backend %s unassigned from user %s", backend.name, user.username)
    return {"message": f"Backend {backend.name} removed from user {user.username}"}


@router.get("/users/{user_id}/api-keys", response_model=list[ApiKeyResponse])
def list_user_api_keys(
    user: User = Depends(get_user),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission(Permission.SYSTEM_MANAGE)),
) -> list[ApiKey]:
    """List API keys owned by a user."""
    return db.scalars(
        select(ApiKey)
        .where(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
    ).all()
