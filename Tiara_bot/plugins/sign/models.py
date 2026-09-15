from nonebot_plugin_orm import Model
from sqlalchemy import BigInteger, Integer, Text, Index, text, desc
from sqlalchemy.orm import Mapped, mapped_column

class UserSign(Model):
    __tablename__ = "user_sign"
    # 自增id作为主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 用户QQ号(唯一索引)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    # 连续签到天数(断签重置为1,从未签到为0)
    sign_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # 累计签到总天数(只增不减,用于排行榜)
    total_sign: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # 上次签到日期(格式:YYYY-MM-DD,用于连续天数判定)
    last_sign_date: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("CURRENT_DATE"))
    # 记录创建时间戳(Unix时间戳)
    created_at: Mapped[int] = mapped_column(Integer, server_default=text("EXTRACT(EPOCH FROM NOW())::INTEGER"))
    
    # 组合索引
    __table_args__ = (
            Index("idx_total_sign", desc("total_sign")),
            )

