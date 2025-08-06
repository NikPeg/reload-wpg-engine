"""
Country model with 9 aspects
"""

from typing import List, Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wpg_engine.models.base import Base


class Country(Base):
    """Country model with 9 strategic aspects"""

    __tablename__ = "countries"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Foreign key to game
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)

    # 9 strategic aspects (1-10 scale)
    economy: Mapped[int] = mapped_column(Integer, default=5)
    military: Mapped[int] = mapped_column(Integer, default=5)
    foreign_policy: Mapped[int] = mapped_column(Integer, default=5)
    territory: Mapped[int] = mapped_column(Integer, default=5)
    technology: Mapped[int] = mapped_column(Integer, default=5)
    religion_culture: Mapped[int] = mapped_column(Integer, default=5)
    governance_law: Mapped[int] = mapped_column(Integer, default=5)
    construction_infrastructure: Mapped[int] = mapped_column(Integer, default=5)
    social_relations: Mapped[int] = mapped_column(Integer, default=5)

    # Additional country data
    capital: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    population: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

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

    # Relationships
    game: Mapped["Game"] = relationship("Game", back_populates="countries")
    players: Mapped[List["Player"]] = relationship("Player", back_populates="country")

    def get_aspects(self) -> dict[str, int]:
        """Get all aspects as dictionary"""
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
        }

    def get_public_aspects(self) -> dict[str, int]:
        """Get only publicly visible aspects"""
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
        }

        return {
            aspect: value for aspect, value in aspects.items() if public_flags[aspect]
        }

    def __repr__(self) -> str:
        return f"<Country(id={self.id}, name='{self.name}', game_id={self.game_id})>"
