"""initial_tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-05-28

إنشاء جميع جداول قاعدة البيانات لأول مرة
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # إنشاء الـ enums أولاً — IF NOT EXISTS يتجاهل الموجود
    op.execute("CREATE TYPE IF NOT EXISTS userrole AS ENUM ('user', 'admin')")
    op.execute("CREATE TYPE IF NOT EXISTS userstatus AS ENUM ('active', 'suspended', 'banned', 'frozen')")
    op.execute("CREATE TYPE IF NOT EXISTS discounttype AS ENUM ('percentage', 'free_days', 'free_plan')")
    op.execute("CREATE TYPE IF NOT EXISTS plantype AS ENUM ('free_trial', 'monthly', 'semi_annual', 'annual', 'custom')")
    op.execute("CREATE TYPE IF NOT EXISTS subscriptionstatus AS ENUM ('active', 'expired', 'cancelled', 'paused')")
    op.execute("CREATE TYPE IF NOT EXISTS replytype AS ENUM ('default', 'custom', 'random')")
    op.execute("CREATE TYPE IF NOT EXISTS dmcondition AS ENUM ('always', 'keywords')")
    op.execute("CREATE TYPE IF NOT EXISTS logstatus AS ENUM ('pending', 'replied', 'dm_sent', 'failed', 'skipped')")

    # --- جدول المستخدمين ---
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('facebook_id', sa.String(50), nullable=False, unique=True),
        sa.Column('facebook_name', sa.String(200), nullable=False),
        sa.Column('facebook_email', sa.String(200), nullable=True),
        sa.Column('facebook_picture_url', sa.String(500), nullable=True),
        sa.Column('facebook_access_token', sa.String(1000), nullable=True),
        sa.Column('facebook_token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('role', sa.Enum('user', 'admin', name='userrole', create_type=False), nullable=False, server_default='user'),
        sa.Column('status', sa.Enum('active', 'suspended', 'banned', 'frozen', name='userstatus', create_type=False), nullable=False, server_default='active'),
        sa.Column('frozen_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('admin_notes', sa.String(1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        if_not_exists=True,
    )
    op.create_index('ix_users_facebook_id', 'users', ['facebook_id'], if_not_exists=True)

    # --- جدول الكوبونات ---
    op.create_table(
        'coupons',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('code', sa.String(50), nullable=False, unique=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('discount_type', sa.Enum('percentage', 'free_days', 'free_plan', name='discounttype', create_type=False), nullable=False),
        sa.Column('discount_value', sa.Float, nullable=False),
        sa.Column('applicable_plan', sa.String(50), nullable=True),
        sa.Column('max_uses', sa.Integer, nullable=True),
        sa.Column('uses_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('one_per_user', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )
    op.create_index('ix_coupons_code', 'coupons', ['code'], if_not_exists=True)

    # --- جدول استخدامات الكوبون ---
    op.create_table(
        'coupon_usages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('coupon_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('coupons.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )

    # --- جدول الصفحات ---
    op.create_table(
        'pages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('facebook_page_id', sa.String(50), nullable=False, unique=True),
        sa.Column('page_name', sa.String(300), nullable=False),
        sa.Column('page_category', sa.String(100), nullable=True),
        sa.Column('page_picture_url', sa.String(500), nullable=True),
        sa.Column('page_followers_count', sa.BigInteger, nullable=False, server_default='0'),
        sa.Column('page_access_token', sa.String(1000), nullable=False),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('had_free_trial', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('free_trial_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('webhook_subscribed', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )
    op.create_index('ix_pages_facebook_page_id', 'pages', ['facebook_page_id'], if_not_exists=True)

    # --- جدول الاشتراكات ---
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, unique=True),
        sa.Column('plan_type', sa.Enum('free_trial', 'monthly', 'semi_annual', 'annual', 'custom', name='plantype', create_type=False), nullable=False),
        sa.Column('status', sa.Enum('active', 'expired', 'cancelled', 'paused', name='subscriptionstatus', create_type=False), nullable=False, server_default='active'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('max_pages', sa.Integer, nullable=False, server_default='1'),
        sa.Column('max_active_campaigns', sa.Integer, nullable=False, server_default='3'),
        sa.Column('max_comments_per_month', sa.Integer, nullable=False, server_default='50'),
        sa.Column('comments_used_this_month', sa.Integer, nullable=False, server_default='0'),
        sa.Column('month_reset_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('admin_override', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('admin_notes', sa.Text, nullable=True),
        sa.Column('last_modified_by_admin', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )

    # --- جدول الحملات ---
    op.create_table(
        'campaigns',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('facebook_post_id', sa.String(100), nullable=False),
        sa.Column('page_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pages.id'), nullable=False),
        sa.Column('post_url', sa.String(500), nullable=True),
        sa.Column('post_preview', sa.String(500), nullable=True),
        sa.Column('reply_type', sa.Enum('default', 'custom', 'random', name='replytype', create_type=False), nullable=False, server_default='default'),
        sa.Column('custom_reply_text', sa.Text, nullable=True),
        sa.Column('random_replies', postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column('send_dm', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('dm_text', sa.Text, nullable=True),
        sa.Column('dm_condition', sa.Enum('always', 'keywords', name='dmcondition', create_type=False), nullable=False, server_default='always'),
        sa.Column('dm_keywords', postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column('reply_all_comments', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('dm_once_per_user', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('total_comments_received', sa.Integer, nullable=False, server_default='0'),
        sa.Column('total_replies_sent', sa.Integer, nullable=False, server_default='0'),
        sa.Column('total_dms_sent', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        if_not_exists=True,
    )
    op.create_index('ix_campaigns_facebook_post_id', 'campaigns', ['facebook_post_id'], if_not_exists=True)

    # --- جدول سجلات التعليقات ---
    op.create_table(
        'comment_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('campaigns.id'), nullable=False),
        sa.Column('facebook_comment_id', sa.String(100), nullable=False, unique=True),
        sa.Column('commenter_facebook_id', sa.String(50), nullable=False),
        sa.Column('commenter_name', sa.String(200), nullable=False),
        sa.Column('comment_text', sa.Text, nullable=False),
        sa.Column('reply_text_sent', sa.Text, nullable=True),
        sa.Column('dm_text_sent', sa.Text, nullable=True),
        sa.Column('status', sa.Enum('pending', 'replied', 'dm_sent', 'failed', 'skipped', name='logstatus', create_type=False), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('dm_already_sent', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        if_not_exists=True,
    )
    op.create_index('ix_comment_logs_facebook_comment_id', 'comment_logs', ['facebook_comment_id'], if_not_exists=True)
    op.create_index('ix_comment_logs_commenter_facebook_id', 'comment_logs', ['commenter_facebook_id'], if_not_exists=True)


def downgrade() -> None:
    op.drop_index('ix_comment_logs_commenter_facebook_id', 'comment_logs')
    op.drop_index('ix_comment_logs_facebook_comment_id', 'comment_logs')
    op.drop_table('comment_logs')
    op.drop_index('ix_campaigns_facebook_post_id', 'campaigns')
    op.drop_table('campaigns')
    op.drop_table('subscriptions')
    op.drop_index('ix_pages_facebook_page_id', 'pages')
    op.drop_table('pages')
    op.drop_table('coupon_usages')
    op.drop_index('ix_coupons_code', 'coupons')
    op.drop_table('coupons')
    op.drop_index('ix_users_facebook_id', 'users')
    op.drop_table('users')
    op.execute("DROP TYPE IF EXISTS logstatus")
    op.execute("DROP TYPE IF EXISTS dmcondition")
    op.execute("DROP TYPE IF EXISTS replytype")
    op.execute("DROP TYPE IF EXISTS subscriptionstatus")
    op.execute("DROP TYPE IF EXISTS plantype")
    op.execute("DROP TYPE IF EXISTS discounttype")
    op.execute("DROP TYPE IF EXISTS userstatus")
    op.execute("DROP TYPE IF EXISTS userrole")
