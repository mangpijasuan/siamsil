"""Editorial Siamsil Dictionary: sources, entries, senses, equivalents, examples and issues

Revision ID: 20261027_0006
Revises: 20261027_0005
Create Date: 2026-10-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '20261027_0006'
down_revision: Union[str, None] = '20261027_0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('dictionary_entries',
    sa.Column('id', sa.String(length=16), nullable=False),
    sa.Column('headword', sa.Text(), nullable=False),
    sa.Column('match_key', sa.Text(), nullable=False),
    sa.Column('part_of_speech', sa.String(length=16), nullable=True),
    sa.Column('pos_key', sa.String(length=16), server_default='', nullable=False),
    sa.Column('entry_type', sa.String(length=8), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='draft', nullable=False),
    sa.Column('merged_into', sa.String(length=16), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(status = 'merged') = (merged_into IS NOT NULL)", name='ck_dictionary_entries_merged'),
    sa.CheckConstraint("entry_type IN ('word', 'term', 'name', 'phrase')", name='ck_dictionary_entries_type'),
    sa.CheckConstraint("id ~ '^ZE-[0-9]{6,}$'", name='ck_dictionary_entries_id'),
    sa.CheckConstraint("status IN ('draft', 'in_review', 'approved', 'published', 'rejected', 'deferred', 'merged')", name='ck_dictionary_entries_status'),
    sa.ForeignKeyConstraint(['merged_into'], ['dictionary_entries.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('match_key', 'pos_key', name='uq_dictionary_entries_key')
    )
    op.create_table('dictionary_sources',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('version', sa.Text(), nullable=True),
    sa.Column('file_name', sa.Text(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('rights_key', sa.String(length=64), nullable=False),
    sa.Column('rights', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('records', sa.Integer(), nullable=False),
    sa.Column('imported_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('dictionary_senses',
    sa.Column('id', sa.String(length=16), nullable=False),
    sa.Column('entry_id', sa.String(length=16), nullable=False),
    sa.Column('source_id', sa.String(length=64), nullable=False),
    sa.Column('source_record_id', sa.Text(), nullable=False),
    sa.Column('sense_number', sa.SmallInteger(), nullable=True),
    sa.Column('definition_en', sa.Text(), nullable=True),
    sa.Column('explanation_ctd', sa.Text(), nullable=True),
    sa.Column('usage_tier', sa.String(length=2), nullable=True),
    sa.Column('domain', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=16), server_default='draft', nullable=False),
    sa.Column('review_status', sa.String(length=16), server_default='unreviewed', nullable=False),
    sa.Column('raw', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("id ~ '^(ZD|ZS)-[0-9]{6,}$'", name='ck_dictionary_senses_id'),
    sa.CheckConstraint("review_status IN ('unreviewed', 'in_review', 'needs_correction', 'approved', 'rejected')", name='ck_dictionary_senses_review_status'),
    sa.CheckConstraint("status IN ('draft', 'in_review', 'approved', 'published', 'rejected', 'deferred')", name='ck_dictionary_senses_status'),
    sa.ForeignKeyConstraint(['entry_id'], ['dictionary_entries.id'], ),
    sa.ForeignKeyConstraint(['source_id'], ['dictionary_sources.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_id', 'source_record_id', name='uq_dictionary_senses_source_record')
    )
    op.create_index(op.f('ix_dictionary_senses_entry_id'), 'dictionary_senses', ['entry_id'], unique=False)
    op.create_index(op.f('ix_dictionary_senses_source_id'), 'dictionary_senses', ['source_id'], unique=False)
    op.create_table('dictionary_equivalents',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
    sa.Column('sense_id', sa.String(length=16), nullable=False),
    sa.Column('language', sa.String(length=8), nullable=False),
    sa.Column('kind', sa.String(length=12), nullable=False),
    sa.Column('position', sa.SmallInteger(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.CheckConstraint("kind IN ('equivalent', 'gloss')", name='ck_dictionary_equivalents_kind'),
    sa.CheckConstraint("language IN ('ctd', 'my')", name='ck_dictionary_equivalents_language'),
    sa.ForeignKeyConstraint(['sense_id'], ['dictionary_senses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sense_id', 'language', 'position', name='uq_dictionary_equivalents_position')
    )
    op.create_index(op.f('ix_dictionary_equivalents_sense_id'), 'dictionary_equivalents', ['sense_id'], unique=False)
    op.create_table('dictionary_examples',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
    sa.Column('sense_id', sa.String(length=16), nullable=False),
    sa.Column('kind', sa.String(length=8), nullable=False),
    sa.Column('position', sa.SmallInteger(), nullable=False),
    sa.Column('english', sa.Text(), nullable=True),
    sa.Column('ctd', sa.Text(), nullable=True),
    sa.CheckConstraint("kind IN ('example', 'phrase')", name='ck_dictionary_examples_kind'),
    sa.ForeignKeyConstraint(['sense_id'], ['dictionary_senses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sense_id', 'kind', 'position', name='uq_dictionary_examples_position')
    )
    op.create_index(op.f('ix_dictionary_examples_sense_id'), 'dictionary_examples', ['sense_id'], unique=False)
    op.create_table('dictionary_issues',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
    sa.Column('source_id', sa.String(length=64), nullable=False),
    sa.Column('source_issue_id', sa.Text(), nullable=False),
    sa.Column('sense_id', sa.String(length=16), nullable=True),
    sa.Column('category', sa.Text(), nullable=True),
    sa.Column('code', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('priority', sa.String(length=16), nullable=True),
    sa.Column('required_reviewer', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=16), server_default='open', nullable=False),
    sa.Column('raw', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('open', 'resolved', 'dismissed')", name='ck_dictionary_issues_status'),
    sa.ForeignKeyConstraint(['sense_id'], ['dictionary_senses.id'], ),
    sa.ForeignKeyConstraint(['source_id'], ['dictionary_sources.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_id', 'source_issue_id', name='uq_dictionary_issues_source_issue')
    )
    op.create_index(op.f('ix_dictionary_issues_sense_id'), 'dictionary_issues', ['sense_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_dictionary_issues_sense_id'), table_name='dictionary_issues')
    op.drop_table('dictionary_issues')
    op.drop_index(op.f('ix_dictionary_examples_sense_id'), table_name='dictionary_examples')
    op.drop_table('dictionary_examples')
    op.drop_index(op.f('ix_dictionary_equivalents_sense_id'), table_name='dictionary_equivalents')
    op.drop_table('dictionary_equivalents')
    op.drop_index(op.f('ix_dictionary_senses_source_id'), table_name='dictionary_senses')
    op.drop_index(op.f('ix_dictionary_senses_entry_id'), table_name='dictionary_senses')
    op.drop_table('dictionary_senses')
    op.drop_table('dictionary_sources')
    op.drop_table('dictionary_entries')
