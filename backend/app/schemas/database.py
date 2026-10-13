"""Agent output contract: Database Agent (AGENT 7)."""

from pydantic import BaseModel, Field


class FieldDef(BaseModel):
    name: str
    type: str = "string"
    primary_key: bool = False
    nullable: bool = True


class RelationDef(BaseModel):
    from_entity: str
    to_entity: str
    type: str = "many-to-one"


class EntityDef(BaseModel):
    name: str
    table: str = ""
    fields: list[FieldDef] = []
    relations: list[RelationDef] = []
    description: str = ""


class DatabaseSchemaResult(BaseModel):
    """Database schema produced by the Database Agent."""

    entities: list[EntityDef] = Field(min_length=1)
    indexes: list[str] = []
    notes: str = ""
