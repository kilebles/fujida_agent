from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def has_user_phone(session: AsyncSession, user_id: int) -> bool:
    user = await get_user_by_id(session, user_id)
    return bool(user and user.phone_number)


async def save_user_phone(session: AsyncSession, user_id: int, first_name: str, phone_number: str) -> None:
    user = await get_user_by_id(session, user_id)

    if user:
        user.phone_number = phone_number
        if not user.first_name:
            user.first_name = first_name
    else:
        user = User(
            id=user_id,
            platform="telegram",
            platform_user_id=str(user_id),
            first_name=first_name,
            phone_number=phone_number,
        )
        session.add(user)

    await session.commit()
