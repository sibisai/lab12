from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

import crud, server.models as models, db
from db import engine
from server.main import create_access_token

router = APIRouter()

@router.post("/register", status_code=201)
async def register(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(db.get_db),
):
    existing = await crud.get_user_by_username(session, form.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    user = await crud.create_user(session, form.username, form.password)
    return {"username": user.username, "created_at": user.created_at}


@router.post("/token")
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(db.get_db),
):
    user = await crud.authenticate_user(session, form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # issue JWT exactly the same way your existing /token did:
    access_token = create_access_token({"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}