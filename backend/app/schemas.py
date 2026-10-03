from typing import Literal
from datetime import date
from pydantic import BaseModel, Field, EmailStr, model_validator


class Strict(BaseModel):
    model_config = {"extra": "forbid"}


class Login(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class Refresh(Strict):
    refresh_token: str = Field(min_length=20, max_length=200)


class ResetRequest(Strict):
    email: EmailStr


class ResetComplete(Strict):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=12, max_length=128)


class SubdistrictIn(Strict):
    name: str = Field(min_length=2, max_length=120)
    code: str | None = None
    responsible_officer: str | None = None
    contact: str | None = None
    active: bool = True


class FacilityIn(Strict):
    name: str = Field(min_length=2, max_length=160)
    code: str | None = Field(default=None, max_length=50)
    facility_type: str = Field(min_length=2, max_length=60)
    subdistrict_id: str
    community: str | None = Field(default=None, max_length=120)
    ownership: str = Field(default="Public", max_length=60)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    active: bool = True
    programmes: list[str] = Field(default_factory=list, max_length=50)


class CommunityIn(Strict):
    name: str = Field(min_length=2, max_length=120)
    facility_id: str
    chps_zone: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    active: bool = True


class Setup(Strict):
    name: str = Field(min_length=3, max_length=180)
    organization_type: str = Field(min_length=2, max_length=80)
    region_id: str
    health_district_name: str = Field(min_length=2, max_length=160)
    subdistricts: list[SubdistrictIn] = Field(min_length=1, max_length=100)
    facilities: list[FacilityIn] = Field(default_factory=list, max_length=1000)
    admin_name: str = Field(min_length=2, max_length=120)
    admin_email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    programmes: list[str] = Field(min_length=1, max_length=50)
    contact: str = Field(default="", max_length=200)
    indicators: list["IndicatorIn"] = Field(default_factory=list, max_length=100)


class MainAdminSetup(Strict):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class UserIn(Strict):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: str
    subdistrict_id: str | None = None
    facility_id: str | None = None
    community_id: str | None = None


class ClientIn(Strict):
    name: str = Field(min_length=2, max_length=120)
    reference: str = Field(min_length=2, max_length=80)
    date_of_birth: date
    sex: Literal["Female", "Male", "Other", "Unknown"]
    facility_id: str
    community_id: str | None = None
    phone: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def birth(self):
        if self.date_of_birth > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return self


class EncounterIn(Strict):
    client_id: str
    programme: str
    visit_date: date
    measurements: dict[str, float | bool | str | None] = Field(default_factory=dict)
    assessment: str = Field(min_length=2, max_length=4000)
    followup_date: date | None = None
    outcome: str | None = Field(default=None, max_length=2000)
    risk: Literal["Routine", "Needs assessment", "High", "Immediate"] = "Routine"

    @model_validator(mode="after")
    def dates(self):
        if self.visit_date > date.today():
            raise ValueError("Visit cannot be in the future")
        if self.followup_date and self.followup_date < self.visit_date:
            raise ValueError("Follow-up precedes visit")
        ranges = {
            "weight_kg": (0.1, 400),
            "height_cm": (10, 250),
            "muac_cm": (5, 60),
            "haemoglobin_g_dl": (1, 25),
            "systolic_mmhg": (40, 300),
            "diastolic_mmhg": (20, 200),
        }
        for key, (lo, hi) in ranges.items():
            value = self.measurements.get(key)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not lo <= value <= hi
            ):
                raise ValueError(f"{key} is outside the accepted entry range")
        return self


class ActionIn(Strict):
    title: str = Field(min_length=3, max_length=180)
    problem: str = Field(min_length=3, max_length=4000)
    facility_id: str | None = None
    client_id: str | None = None
    indicator_id: str | None = None
    assigned_to: str | None = None
    due_date: date
    priority: Literal["Low", "Medium", "High", "Urgent"] = "Medium"


class ActionUpdate(Strict):
    status: Literal["Open", "In progress", "Completed", "Cancelled"]
    outcome: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def completion(self):
        if self.status == "Completed" and not self.outcome:
            raise ValueError("Record the outcome before completion")
        return self


class IndicatorIn(Strict):
    standard_id: str | None = None
    name: str = Field(min_length=3, max_length=160)
    programme: str
    definition: str = Field(min_length=5, max_length=2000)
    numerator_definition: str = Field(min_length=3, max_length=1000)
    denominator_definition: str = Field(min_length=3, max_length=1000)
    target: float = Field(ge=0, le=100)
    direction: Literal["higher", "lower"] = "higher"
    approval_reference: str = Field(min_length=3, max_length=250)


class IndicatorValue(Strict):
    indicator_id: str
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)

    @model_validator(mode="after")
    def ratio(self):
        if self.numerator > self.denominator:
            raise ValueError("Numerator exceeds denominator")
        return self


class ReportIn(Strict):
    facility_id: str
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    values: list[IndicatorValue] = Field(min_length=1, max_length=200)


class Transition(Strict):
    state: Literal["Draft", "Submitted", "Returned", "Verified", "Approved", "Locked"]
    reason: str = Field(default="", max_length=2000)


class Amendment(Strict):
    reason: str = Field(min_length=10, max_length=2000)


class RecordIn(Strict):
    title: str = Field(min_length=3, max_length=180)
    facility_id: str | None = None
    details: dict = Field(default_factory=dict)


class ConfigurationIn(Strict):
    programmes: list[str] = Field(min_length=1, max_length=50)
    facility_types: list[str] = Field(min_length=1, max_length=50)
    report_header: str = Field(max_length=250)
    contact: str = Field(max_length=250)
    reporting_officer: str = Field(default="", max_length=120)
    logo_url: str = Field(default="", max_length=500)
    quality_weights: dict[str, float] = Field(
        default_factory=lambda: {"Completeness": 1, "Timeliness": 1, "Validity": 1}
    )
    report_deadline_day: int = Field(default=5, ge=1, le=28)
    deterioration_threshold_pp: float = Field(default=5, ge=0.1, le=100)
    supervision_checklist: list[str] = Field(default_factory=list, max_length=100)
    approval_workflow: list[str] = Field(
        default_factory=lambda: ["Draft", "Submitted", "Verified", "Approved", "Locked"]
    )

    @model_validator(mode="after")
    def quality_policy(self):
        if self.approval_workflow not in (
            ["Draft", "Submitted", "Verified", "Approved", "Locked"],
            ["Draft", "Submitted", "Approved", "Locked"],
        ):
            raise ValueError("Use the standard approval workflow, with verification optionally required")
        if (
            not {"Completeness", "Timeliness", "Validity"} <= set(self.quality_weights)
            or not set(self.quality_weights)
            <= {"Completeness", "Timeliness", "Validity", "Consistency", "Duplicate rate"}
            or any(w < 0 or w > 100 for w in self.quality_weights.values())
            or sum(self.quality_weights.values()) <= 0
        ):
            raise ValueError(
                "Configure positive quality weight totals for the three measured components"
            )
        return self


class OrganizationProvision(Setup):
    password: str | None = Field(default=None, min_length=12, max_length=128)


class StaffProvision(Strict):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    role: str
    level: Literal["NATIONAL", "REGION", "ORGANIZATION"]
    region_id: str | None = None
    organization_id: str | None = None
    subdistrict_id: str | None = None
    facility_id: str | None = None
    community_id: str | None = None


class UserStatus(Strict):
    active: bool


class LocalStatus(Strict):
    active: bool


class ProgrammeIn(Strict):
    code: str = Field(pattern=r"^[a-z][a-z0-9-]{1,59}$")
    name: str = Field(min_length=3, max_length=120)
    active: bool = True
    approval_reference: str = Field(default="", max_length=250)
    fields: list[dict] = Field(default_factory=list, max_length=40)


Setup.model_rebuild()


class StandardIndicatorIn(IndicatorIn):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,59}$")
    version: str = Field(min_length=1, max_length=40)
    source_url: str = Field(min_length=5, max_length=500)
    target: float | None = Field(default=None, ge=0, le=100)


class SignalActionIn(Strict):
    indicator_id: str
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    assigned_to: str
    due_date: date
    problem: str = Field(min_length=10, max_length=4000)
    facility_id: str | None = None


class RegionChange(Strict):
    name: str = Field(min_length=2, max_length=100)
    region_code: str = Field(min_length=1, max_length=40)
    capital: str | None = Field(default=None, max_length=100)
    active: bool = True
    source: str = Field(min_length=5, max_length=2000)
    version: str = Field(min_length=2, max_length=60)
    source_date: date


class OfflineEncounterIn(Strict):
    operation_id: str = Field(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    encounter: EncounterIn


class ReportJobIn(Strict):
    format: Literal["pdf", "xlsx"]
