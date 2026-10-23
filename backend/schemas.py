from datetime import date
from pydantic import BaseModel, Field


class FarmUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    location: str = Field(min_length=2, max_length=150)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    timezone: str | None = Field(default=None, min_length=3, max_length=80)


class PlotUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    acreage: float = Field(gt=0, le=20)
    crop: str = Field(min_length=2, max_length=80)
    planting_date: date
    expected_harvest_date: date
    expected_yield: float = Field(ge=0)
    actual_yield: float | None = Field(default=None, ge=0)
    status: str = Field(min_length=2, max_length=30)
    estimated_cost: float = Field(ge=0)
    expected_revenue: float = Field(ge=0)


class FinancialTransactionCreate(BaseModel):
    transaction_date: date
    transaction_type: str
    category: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=2, max_length=200)
    amount: float = Field(ge=0)
    product_id: str | None = None
    asset_id: str | None = None
    vendor_customer: str | None = None
    classification: str = "ACTUAL"
    cash_accrual: str = "CASH"
    source_note: str | None = None


class InvestmentAssumptions(BaseModel):
    project_name: str = Field(min_length=2, max_length=120)
    initial_investment: float = Field(ge=0)
    lifespan_years: int = Field(gt=0, le=50)
    annual_incremental_revenue: float = Field(ge=0)
    annual_operating_costs: float = Field(ge=0)
    annual_maintenance: float = Field(ge=0)
    working_capital: float = Field(ge=0)
    working_capital_recovery: float = Field(ge=0)
    residual_value: float = Field(ge=0)
    discount_rate: float = Field(gt=-1, le=2)
    tax_rate: float = Field(ge=0, le=1, default=0)


class PricingScenarioInput(BaseModel):
    product_id: str
    target_margin: float = Field(ge=0, lt=1)
    market_reference: float | None = Field(default=None, ge=0)
    seasonality_factor: float = Field(gt=0)
    supply_factor: float = Field(ge=0)
    selling_price: float = Field(ge=0)
    expected_volume: float = Field(ge=0)
    sales_volume: float | None = Field(default=None, ge=0)
    estimated_spoilage: float = Field(ge=0, le=1)
    objective: str = "margin_preservation"
    inventory_age_days: int = Field(default=0, ge=0)
    weather_supply_factor: float = Field(gt=0)


class PriceApproval(BaseModel):
    price: float = Field(ge=0)
    effective_start: date
    effective_end: date | None = None
    approved_by: str = Field(min_length=2, max_length=100)
    reason: str = Field(min_length=2, max_length=300)


class InventoryAction(BaseModel):
    quantity: float = Field(gt=0)
    reason: str = Field(min_length=2, max_length=240)
    created_by: str = Field(min_length=2, max_length=100)
    reference_id: str | None = Field(default=None, max_length=120)


class InventoryLotCreate(BaseModel):
    product_id: str
    origin_asset_id: str | None = None
    lot_type: str = Field(pattern="^(CROP|DAIRY)$")
    production_date: date
    quantity_produced: float = Field(gt=0)
    quantity_unit: str = Field(min_length=2, max_length=20)
    quality_grade: str | None = Field(default=None, max_length=20)
    storage_id: str | None = None
    sell_by_date: date | None = None
    created_by: str = Field(min_length=2, max_length=100)
    reason: str = Field(min_length=2, max_length=240)


class ReservationCreate(InventoryAction):
    buyer_reference: str | None = Field(default=None, max_length=160)
    expires_at: date | None = None


class AnimalCreate(BaseModel):
    tag: str = Field(min_length=2, max_length=30)
    name: str | None = Field(default=None, max_length=80)
    breed: str | None = Field(default=None, max_length=80)
    birth_date: date | None = None
    sex: str = Field(default="FEMALE", min_length=1, max_length=20)
    herd_category: str = Field(default="LACTATING_COW", min_length=2, max_length=40)
    production_status: str = Field(default="MILKING", min_length=2, max_length=30)
    facility_id: str | None = None
    notes: str | None = Field(default=None, max_length=300)


class AnimalUpdate(AnimalCreate):
    tag: str = Field(default="", max_length=30)


class DairyProductionCreate(BaseModel):
    production_date: date
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=2, max_length=20)
    session_type: str = Field(default="DAILY", min_length=2, max_length=20)
    processing_status: str = Field(default="RAW", min_length=2, max_length=30)
    saleable_quantity: float = Field(ge=0)
    withheld_quantity: float = Field(default=0, ge=0)
    withholding_reason: str | None = Field(default=None, max_length=240)
    operator: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=300)


class MilkCollectionCreate(BaseModel):
    collection_date: date
    source_scope: str = Field(default="MILKING_HERD", min_length=2, max_length=80)
    quantity_collected: float = Field(gt=0)
    unit: str = Field(default="liter", min_length=2, max_length=20)
    approved_quantity: float | None = Field(default=None, ge=0)
    withheld_quantity: float = Field(default=0, ge=0)
    withholding_reason: str | None = Field(default=None, max_length=240)
    storage_id: str | None = None
    temperature_f: float | None = None
    quality_status: str = Field(default="PENDING", min_length=2, max_length=30)
    sell_by_date: date | None = None
    notes: str | None = Field(default=None, max_length=300)
    created_by: str = Field(default="Farm owner", min_length=2, max_length=100)


class DairyProcessingCreate(BaseModel):
    input_lot_id: str
    product_id: str
    input_quantity: float = Field(gt=0)
    processed_at: date
    created_by: str = Field(default="Farm owner", min_length=2, max_length=100)


class FeedPurchaseCreate(BaseModel):
    feed_type: str = Field(min_length=2, max_length=80)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)
    cost_per_unit: float = Field(ge=0)
    dry_matter_pct: float | None = Field(default=None, ge=0, le=1)
    received_date: date
    supplier: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=300)


class FeedUsageCreate(BaseModel):
    usage_date: date
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)
    herd_group: str = Field(min_length=2, max_length=60)
    notes: str | None = Field(default=None, max_length=300)


class DairyTaskCreate(BaseModel):
    category: str = Field(min_length=2, max_length=50)
    priority: str = Field(default="MEDIUM", min_length=2, max_length=20)
    assigned_worker: str | None = Field(default=None, max_length=100)
    due_date: date
    animal_id: str | None = None
    facility_id: str | None = None
    title: str = Field(min_length=2, max_length=160)
    completion_notes: str | None = Field(default=None, max_length=300)


class DairyTaskUpdate(BaseModel):
    status: str = Field(min_length=2, max_length=30)
    completion_notes: str | None = Field(default=None, max_length=300)


class DairyHealthCreate(BaseModel):
    record_date: date
    record_type: str = Field(min_length=2, max_length=50)
    observation: str = Field(min_length=2, max_length=500)
    veterinary_review_required: bool = False
    milk_withdrawal_until: date | None = None
    recorded_by: str = Field(min_length=2, max_length=100)


class PoultryFlockCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    breed: str = Field(min_length=2, max_length=80)
    hens_count: int = Field(ge=0, le=100000)
    roosters_count: int = Field(default=0, ge=0, le=10000)
    chicks_count: int = Field(default=0, ge=0, le=100000)
    hatch_date: date | None = None
    production_status: str = Field(default="LAYING", min_length=2, max_length=30)
    facility_id: str = Field(default="facility-coop", min_length=2, max_length=80)
    expected_laying_rate: float = Field(default=0.80, ge=0, le=1)
    notes: str | None = Field(default=None, max_length=300)


class PoultryFlockUpdate(PoultryFlockCreate):
    pass


class EggCollectionCreate(BaseModel):
    collection_date: date
    collection_time: str = Field(default="AM", min_length=2, max_length=30)
    flock_id: str
    eggs_collected: int = Field(gt=0, le=100000)
    broken_eggs: int = Field(default=0, ge=0)
    dirty_rejected: int = Field(default=0, ge=0)
    worker: str = Field(default="Farm owner", min_length=2, max_length=100)
    notes: str | None = Field(default=None, max_length=300)


class EggPackagingCreate(BaseModel):
    batch_id: str
    package_type: str = Field(pattern="^(SINGLE|HALF_DOZEN|DOZEN|CASE)$")
    package_count: int = Field(gt=0, le=100000)
    packaging_date: date
    storage_id: str = Field(default="storage-egg-room", min_length=2, max_length=80)
    quality_status: str = Field(default="UNVERIFIED", min_length=2, max_length=30)
    created_by: str = Field(default="Farm owner", min_length=2, max_length=100)
    notes: str | None = Field(default=None, max_length=300)


class PoultryFeedPurchaseCreate(BaseModel):
    feed_type: str = Field(min_length=2, max_length=80)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)
    cost_per_unit: float = Field(ge=0)
    received_date: date
    supplier: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=300)


class PoultryFeedUsageCreate(BaseModel):
    usage_date: date
    flock_id: str
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)
    notes: str | None = Field(default=None, max_length=300)


class PoultryTaskCreate(BaseModel):
    category: str = Field(min_length=2, max_length=50)
    priority: str = Field(default="MEDIUM", min_length=2, max_length=20)
    assigned_worker: str | None = Field(default=None, max_length=100)
    due_date: date
    flock_id: str | None = None
    facility_id: str | None = None
    title: str = Field(min_length=2, max_length=160)
    completion_notes: str | None = Field(default=None, max_length=300)


class PoultryTaskUpdate(BaseModel):
    status: str = Field(min_length=2, max_length=30)
    completion_notes: str | None = Field(default=None, max_length=300)


class PoultryHealthCreate(BaseModel):
    event_date: date
    event_type: str = Field(min_length=2, max_length=60)
    observation: str = Field(min_length=2, max_length=500)
    veterinary_review_required: bool = False
    product_hold: bool = False
    recorded_by: str = Field(min_length=2, max_length=100)


class AnimalLegacyUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    production_status: str = Field(min_length=2, max_length=30)
    notes: str | None = Field(default=None, max_length=300)


class MilkProductionCreate(BaseModel):
    production_date: date
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=2, max_length=20)
    processing_status: str = Field(default="RAW", min_length=2, max_length=30)
    saleable_quantity: float = Field(ge=0)
    notes: str | None = Field(default=None, max_length=300)


class BuyerCreate(BaseModel):
    business_name: str = Field(min_length=2, max_length=140)
    category: str = Field(min_length=2, max_length=60)
    contact_name: str | None = Field(default=None, max_length=100)
    contact_role: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    contact_verification_status: str = "UNVERIFIED"
    delivery_preferences: str | None = Field(default=None, max_length=240)
    minimum_order_quantity: float = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=500)


class OfferLineInput(BaseModel):
    product_id: str
    lot_id: str
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=2, max_length=20)
    quality_grade: str | None = None
    unit_price: float | None = Field(default=None, ge=0)


class OfferCreate(BaseModel):
    buyer_id: str
    proposed_delivery_date: date
    expiration_date: date | None = None
    payment_terms: str = Field(default="Payment terms to be agreed", max_length=200)
    delivery_terms: str = Field(default="Delivery terms to be agreed", max_length=200)
    notes: str | None = Field(default=None, max_length=500)
    lines: list[OfferLineInput] = Field(min_length=1, max_length=20)


class PipelineUpdate(BaseModel):
    stage: str
    owner_notes: str | None = Field(default=None, max_length=500)
    next_action: str | None = Field(default=None, max_length=240)


class OrderConfirm(BaseModel):
    buyer_confirmation_reference: str = Field(min_length=2, max_length=160)
    created_by: str = Field(min_length=2, max_length=100)


class AgentRunRequest(BaseModel):
    request: str = Field(min_length=5, max_length=4000)


