"""
Country model with 9 aspects
"""

from sqlalchemy import ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wpg_engine.models.base import Base


class Country(Base):
    """Country model with 9 strategic aspects"""

    __tablename__ = "countries"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Foreign key to game
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)

    # 9 strategic aspects (1-10 scale) with text descriptions
    economy: Mapped[int] = mapped_column(Integer, default=5)
    economy_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    military: Mapped[int] = mapped_column(Integer, default=5)
    military_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    foreign_policy: Mapped[int] = mapped_column(Integer, default=5)
    foreign_policy_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    territory: Mapped[int] = mapped_column(Integer, default=5)
    territory_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    technology: Mapped[int] = mapped_column(Integer, default=5)
    technology_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    religion_culture: Mapped[int] = mapped_column(Integer, default=5)
    religion_culture_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    governance_law: Mapped[int] = mapped_column(Integer, default=5)
    governance_law_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    construction_infrastructure: Mapped[int] = mapped_column(Integer, default=5)
    construction_infrastructure_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    social_relations: Mapped[int] = mapped_column(Integer, default=5)
    social_relations_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    intelligence: Mapped[int] = mapped_column(Integer, default=5)
    intelligence_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Additional country data
    capital: Mapped[str | None] = mapped_column(String(255), nullable=True)
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Synonyms for country name (list of strings, editable by admin only)
    synonyms: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    # Public visibility flags for each aspect
    economy_public: Mapped[bool] = mapped_column(default=True)
    military_public: Mapped[bool] = mapped_column(default=False)
    foreign_policy_public: Mapped[bool] = mapped_column(default=True)
    territory_public: Mapped[bool] = mapped_column(default=True)
    technology_public: Mapped[bool] = mapped_column(default=True)
    religion_culture_public: Mapped[bool] = mapped_column(default=True)
    governance_law_public: Mapped[bool] = mapped_column(default=True)
    construction_infrastructure_public: Mapped[bool] = mapped_column(default=True)
    social_relations_public: Mapped[bool] = mapped_column(default=True)
    intelligence_public: Mapped[bool] = mapped_column(default=False)  # Разведка по умолчанию скрыта

    # Relationships
    game: Mapped["Game"] = relationship("Game", back_populates="countries")
    players: Mapped[list["Player"]] = relationship("Player", back_populates="country")

    def get_aspects(self) -> dict[str, dict]:
        """Get all aspects with values and descriptions"""
        return {
            "economy": {"value": self.economy, "description": self.economy_description},
            "military": {
                "value": self.military,
                "description": self.military_description,
            },
            "foreign_policy": {
                "value": self.foreign_policy,
                "description": self.foreign_policy_description,
            },
            "territory": {
                "value": self.territory,
                "description": self.territory_description,
            },
            "technology": {
                "value": self.technology,
                "description": self.technology_description,
            },
            "religion_culture": {
                "value": self.religion_culture,
                "description": self.religion_culture_description,
            },
            "governance_law": {
                "value": self.governance_law,
                "description": self.governance_law_description,
            },
            "construction_infrastructure": {
                "value": self.construction_infrastructure,
                "description": self.construction_infrastructure_description,
            },
            "social_relations": {
                "value": self.social_relations,
                "description": self.social_relations_description,
            },
            "intelligence": {
                "value": self.intelligence,
                "description": self.intelligence_description,
            },
        }

    def get_aspects_values_only(self) -> dict[str, int]:
        """Get all aspects as dictionary with values only (for backward compatibility)"""
        return {
            "economy": self.economy,
            "military": self.military,
            "foreign_policy": self.foreign_policy,
            "territory": self.territory,
            "technology": self.technology,
            "religion_culture": self.religion_culture,
            "governance_law": self.governance_law,
            "construction_infrastructure": self.construction_infrastructure,
            "social_relations": self.social_relations,
            "intelligence": self.intelligence,
        }

    def get_public_aspects(self) -> dict[str, dict]:
        """Get only publicly visible aspects with values and descriptions"""
        aspects = self.get_aspects()
        public_flags = {
            "economy": self.economy_public,
            "military": self.military_public,
            "foreign_policy": self.foreign_policy_public,
            "territory": self.territory_public,
            "technology": self.technology_public,
            "religion_culture": self.religion_culture_public,
            "governance_law": self.governance_law_public,
            "construction_infrastructure": self.construction_infrastructure_public,
            "social_relations": self.social_relations_public,
            "intelligence": self.intelligence_public,
        }

        return {aspect: data for aspect, data in aspects.items() if public_flags[aspect]}

    def __repr__(self) -> str:
        return f"<Country(id={self.id}, name='{self.name}', game_id={self.game_id})>"
