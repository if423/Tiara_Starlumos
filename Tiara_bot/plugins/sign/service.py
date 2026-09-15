from datetime import date, timedelta
from sqlalchemy import select
from nonebot_plugin_orm import async_scoped_session
from .models import UserSign

async def get_sign_in(session: async_scoped_session, user_id: int):
    stmt = select(UserSign).where(UserSign.user_id == user_id)
    user = await session.scalar(stmt)

    today = date.today()
    
    if not user:
        user = UserSign(
                user_id=user_id,
                sign_count=1,
                total_sign=1,
                last_sign_date=str(today)
                )
        session.add(user)
    else:
        last_date = user.last_sign_date
        if last_date == str(today):
            return "今天已经签到过了！"
        elif last_date == str(today - timedelta(days=1)):
            user.sign_count += 1
        else:
            user.sign_count = 1

        user.total_sign += 1
        user.last_sign_date = str(today)
        
    user_sign_count = user.sign_count
    user_total_sign = user.total_sign

    await session.commit()
    return f"签到成功！连续签到{user_sign_count}天,累计签到{user_total_sign}天！"

