from datetime import date, datetime, timezone
from pathlib import Path
import sqlite3

from .config import DATABASE_PATH


def enrich_crop_rows(conn: sqlite3.Connection) -> None:
    specs = {
        "Tomatoes": ("FRUIT", "04-15", "06-15", "07-15", "10-01", 80, 50, 65, 85, 32, 90, 1.25, 12000, "FRUITING", "ACTIVE"),
        "Lettuce": ("LEAFY_GREEN", "03-15", "09-15", "05-01", "10-31", 45, 35, 50, 72, 28, 80, 1.0, 9000, "GROWING", "ACTIVE"),
        "Spinach": ("LEAFY_GREEN", "03-01", "09-15", "04-01", "10-15", 40, 30, 45, 68, 20, 75, 0.9, 7000, "HARVESTED", "ACTIVE"),
        "Carrots": ("ROOT", "03-15", "07-15", "06-15", "11-15", 70, 40, 55, 75, 28, 85, 1.0, 14000, "GROWING", "ACTIVE"),
        "Potatoes": ("ROOT", "04-01", "06-01", "07-15", "10-15", 90, 40, 55, 75, 30, 85, 1.1, 13000, "GROWING", "ACTIVE"),
        "Strawberries": ("FRUIT", "03-15", "05-15", "06-01", "07-15", 120, 35, 55, 80, 28, 85, 1.2, 9000, "FRUITING", "ACTIVE"),
        "Sweet Corn": ("GRAIN", "05-01", "06-30", "07-15", "09-30", 75, 50, 60, 85, 32, 95, 1.25, 11000, "GROWING", "ACTIVE"),
        "Cucumbers": ("FRUIT", "05-01", "06-30", "07-01", "09-15", 55, 55, 65, 85, 35, 95, 1.3, 12000, "GROWING", "ACTIVE"),
    }
    for name, spec in specs.items():
        conn.execute("""UPDATE crops SET category=?, planting_window_start=?, planting_window_end=?, harvest_window_start=?, harvest_window_end=?, maturity_days=?, minimum_temperature_f=?, preferred_temperature_min_f=?, preferred_temperature_max_f=?, frost_tolerance_f=?, heat_sensitivity_f=?, water_requirement_in_week=?, yield_per_acre=?, growth_stage=?, production_status=?, agronomic_source=? WHERE name=?""", (*spec, "Northeast U.S. configurable demonstration assumption; verify locally before operational use.", name))


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS farms (
  farm_id TEXT PRIMARY KEY, name TEXT NOT NULL, location TEXT NOT NULL,
  acreage REAL NOT NULL CHECK (acreage > 0), farm_type TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'SYNTHETIC', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assets (
  asset_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  asset_type TEXT NOT NULL, name TEXT NOT NULL, acreage REAL NOT NULL DEFAULT 0 CHECK (acreage >= 0),
  svg_ref TEXT, status TEXT NOT NULL DEFAULT 'ACTIVE', source_type TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS crops (
  crop_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, variety TEXT, source_type TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS production_plans (
  plan_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  asset_id TEXT NOT NULL REFERENCES assets(asset_id), crop_id TEXT NOT NULL REFERENCES crops(crop_id),
  planting_date TEXT NOT NULL, expected_harvest_date TEXT NOT NULL, expected_yield REAL NOT NULL CHECK (expected_yield >= 0),
  actual_yield REAL, status TEXT NOT NULL, estimated_cost REAL NOT NULL DEFAULT 0 CHECK (estimated_cost >= 0),
  expected_revenue REAL NOT NULL DEFAULT 0 CHECK (expected_revenue >= 0), source_type TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS products (
  product_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, category TEXT NOT NULL, unit TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS dairy_summary (
  dairy_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  herd_size INTEGER NOT NULL CHECK (herd_size >= 0), milking_count INTEGER NOT NULL CHECK (milking_count >= 0),
  daily_milk_liters REAL NOT NULL CHECK (daily_milk_liters >= 0), product_id TEXT REFERENCES products(product_id), source_type TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS expenses (
  expense_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  category TEXT NOT NULL, amount REAL NOT NULL CHECK (amount >= 0), expense_date TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS activities (
  activity_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  activity_date TEXT NOT NULL, title TEXT NOT NULL, detail TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS weather_snapshots (
  weather_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  provider TEXT NOT NULL, data_status TEXT NOT NULL, retrieved_at TEXT NOT NULL,
  forecast_updated_at TEXT, payload_json TEXT NOT NULL, source_url TEXT
);
CREATE TABLE IF NOT EXISTS weather_risks (
  risk_id TEXT PRIMARY KEY, weather_id TEXT NOT NULL REFERENCES weather_snapshots(weather_id) ON DELETE CASCADE,
  farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, asset_id TEXT, crop_id TEXT,
  operation TEXT NOT NULL, forecast_time TEXT NOT NULL, condition TEXT NOT NULL, threshold TEXT NOT NULL,
  forecast_value REAL, severity TEXT NOT NULL, explanation TEXT NOT NULL, recommended_action TEXT NOT NULL,
  source_reference TEXT NOT NULL, forecast_timestamp TEXT NOT NULL, event_key TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS farm_missions (
  mission_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  risk_id TEXT REFERENCES weather_risks(risk_id), event_key TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
  description TEXT NOT NULL, asset_id TEXT, crop_id TEXT, risk_category TEXT NOT NULL,
  priority TEXT NOT NULL, suggested_deadline TEXT NOT NULL, recommended_action TEXT NOT NULL,
  source_reference TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Suggested', created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL, audit_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS financial_transactions (
  transaction_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  transaction_date TEXT NOT NULL, transaction_type TEXT NOT NULL CHECK (transaction_type IN ('EXPENSE','REVENUE')),
  category TEXT NOT NULL, description TEXT NOT NULL, amount REAL NOT NULL CHECK (amount >= 0),
  product_id TEXT, asset_id TEXT, facility_id TEXT, dairy_id TEXT, vendor_customer TEXT,
  classification TEXT NOT NULL CHECK (classification IN ('ACTUAL','BUDGET','FORECAST')),
  cash_accrual TEXT NOT NULL DEFAULT 'CASH', source_note TEXT, source_type TEXT NOT NULL DEFAULT 'SYNTHETIC',
  created_at TEXT NOT NULL, UNIQUE(farm_id,transaction_date,transaction_type,category,description,amount)
);
CREATE TABLE IF NOT EXISTS budgets (
  budget_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  period_start TEXT NOT NULL, period_end TEXT NOT NULL, budget_type TEXT NOT NULL CHECK (budget_type IN ('EXPENSE','REVENUE')),
  category TEXT NOT NULL, budgeted_amount REAL NOT NULL CHECK (budgeted_amount >= 0), product_id TEXT, asset_id TEXT,
  source_type TEXT NOT NULL DEFAULT 'SYNTHETIC', UNIQUE(farm_id,period_start,period_end,budget_type,category,product_id,asset_id)
);
CREATE TABLE IF NOT EXISTS cost_allocations (
  allocation_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  category TEXT NOT NULL, amount REAL NOT NULL CHECK (amount >= 0), method TEXT NOT NULL,
  basis_value REAL NOT NULL CHECK (basis_value >= 0), effective_start TEXT NOT NULL, effective_end TEXT NOT NULL,
  product_id TEXT, asset_id TEXT, assumption_note TEXT, source_type TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS capital_assets (
  capital_asset_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  category TEXT NOT NULL, description TEXT NOT NULL, acquisition_date TEXT NOT NULL, purchase_price REAL NOT NULL CHECK (purchase_price >= 0),
  useful_life_years REAL NOT NULL CHECK (useful_life_years > 0), residual_value REAL NOT NULL DEFAULT 0 CHECK (residual_value >= 0),
  depreciation_method TEXT NOT NULL DEFAULT 'STRAIGHT_LINE', maintenance_cost_annual REAL NOT NULL DEFAULT 0,
  facility_id TEXT, operation_note TEXT, source_type TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS investment_scenarios (
  scenario_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  project_name TEXT NOT NULL, assumptions_json TEXT NOT NULL, results_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'DRAFT', formula_version TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pricing_configs (
  product_id TEXT PRIMARY KEY, product_category TEXT NOT NULL, unit TEXT NOT NULL, production_cost_per_unit REAL NOT NULL CHECK (production_cost_per_unit >= 0),
  current_approved_price REAL, recommended_price REAL, minimum_acceptable_price REAL NOT NULL CHECK (minimum_acceptable_price >= 0),
  target_gross_margin REAL NOT NULL CHECK (target_gross_margin >= 0 AND target_gross_margin < 1), expected_volume REAL NOT NULL DEFAULT 0,
  available_inventory REAL NOT NULL DEFAULT 0, shelf_life_days INTEGER, market_benchmark REAL, seasonal_adjustment REAL NOT NULL DEFAULT 1,
  supply_adjustment REAL NOT NULL DEFAULT 1, last_price_update TEXT, source_type TEXT NOT NULL DEFAULT 'SYNTHETIC', confidence TEXT NOT NULL DEFAULT 'DEMO_ASSUMPTION'
);
CREATE TABLE IF NOT EXISTS market_observations (
  observation_id TEXT PRIMARY KEY, product_id TEXT NOT NULL, source TEXT NOT NULL, report_identifier TEXT, variety_grade TEXT,
  market_location TEXT, observation_date TEXT NOT NULL, price REAL NOT NULL CHECK (price >= 0), quoted_unit TEXT NOT NULL,
  package_size REAL, normalized_unit TEXT NOT NULL, normalized_price REAL NOT NULL CHECK (normalized_price >= 0), conversion_method TEXT NOT NULL,
  source_url TEXT, classification TEXT NOT NULL CHECK (classification IN ('OBSERVED','MANUAL','SYNTHETIC')), freshness_status TEXT NOT NULL DEFAULT 'CURRENT'
);
CREATE TABLE IF NOT EXISTS seasonality_factors (
  factor_id TEXT PRIMARY KEY, product_id TEXT NOT NULL, month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12), season_label TEXT NOT NULL,
  factor REAL NOT NULL CHECK (factor > 0), availability_factor REAL NOT NULL CHECK (availability_factor >= 0), source_note TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'SYNTHETIC', UNIQUE(product_id,month)
);
CREATE TABLE IF NOT EXISTS pricing_recommendations (
  recommendation_id TEXT PRIMARY KEY, product_id TEXT NOT NULL, created_at TEXT NOT NULL, formula_version TEXT NOT NULL,
  inputs_json TEXT NOT NULL, cost_floor REAL NOT NULL, target_margin_price REAL NOT NULL, market_indicated_price REAL,
  recommended_price REAL NOT NULL, expected_gross_margin REAL NOT NULL, conflict_warning TEXT, confidence TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PROPOSED', source_type TEXT NOT NULL DEFAULT 'CALCULATED'
);
CREATE TABLE IF NOT EXISTS pricing_scenarios (
  scenario_id TEXT PRIMARY KEY, product_id TEXT NOT NULL, name TEXT NOT NULL, inputs_json TEXT NOT NULL, results_json TEXT NOT NULL,
  created_at TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED'
);
CREATE TABLE IF NOT EXISTS approved_prices (
  approved_price_id TEXT PRIMARY KEY, product_id TEXT NOT NULL, price REAL NOT NULL CHECK (price >= 0), effective_start TEXT NOT NULL,
  effective_end TEXT, approved_by TEXT NOT NULL, recommendation_id TEXT, reason TEXT, created_at TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED'
);
CREATE TABLE IF NOT EXISTS pricing_change_history (
  change_id TEXT PRIMARY KEY, product_id TEXT NOT NULL, old_price REAL, new_price REAL NOT NULL, action TEXT NOT NULL,
  reason TEXT, approved_price_id TEXT, changed_at TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED'
);
CREATE TABLE IF NOT EXISTS storage_facilities (
  storage_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  facility_id TEXT REFERENCES assets(asset_id), facility_type TEXT NOT NULL, capacity REAL NOT NULL CHECK (capacity >= 0),
  capacity_unit TEXT NOT NULL, applicable_product_types TEXT, storage_conditions TEXT, source_type TEXT NOT NULL DEFAULT 'SYNTHETIC',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inventory_lots (
  lot_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  product_id TEXT NOT NULL REFERENCES products(product_id), origin_asset_id TEXT REFERENCES assets(asset_id),
  lot_type TEXT NOT NULL CHECK (lot_type IN ('CROP','DAIRY')), production_date TEXT NOT NULL, quantity_produced REAL NOT NULL CHECK (quantity_produced >= 0),
  quantity_unit TEXT NOT NULL, quality_grade TEXT, storage_id TEXT REFERENCES storage_facilities(storage_id),
  sell_by_date TEXT, lot_status TEXT NOT NULL DEFAULT 'AVAILABLE', provenance TEXT NOT NULL DEFAULT 'SYNTHETIC',
  source_type TEXT NOT NULL DEFAULT 'SYNTHETIC', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inventory_movements (
  movement_id TEXT PRIMARY KEY, lot_id TEXT NOT NULL REFERENCES inventory_lots(lot_id) ON DELETE CASCADE,
  movement_at TEXT NOT NULL, movement_type TEXT NOT NULL, quantity REAL NOT NULL CHECK (quantity > 0), unit TEXT NOT NULL,
  reason TEXT NOT NULL, reference_id TEXT, created_by TEXT NOT NULL, audit_at TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED',
  UNIQUE(lot_id, movement_type, reference_id)
);
CREATE TABLE IF NOT EXISTS inventory_reservations (
  reservation_id TEXT PRIMARY KEY, lot_id TEXT NOT NULL REFERENCES inventory_lots(lot_id) ON DELETE CASCADE,
  buyer_reference TEXT, quantity REAL NOT NULL CHECK (quantity > 0), status TEXT NOT NULL CHECK (status IN ('ACTIVE','RELEASED','FULFILLED','EXPIRED')),
  created_at TEXT NOT NULL, expires_at TEXT, created_by TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED'
);
CREATE TABLE IF NOT EXISTS dairy_animals (
  animal_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, tag TEXT NOT NULL UNIQUE,
  name TEXT, species TEXT NOT NULL DEFAULT 'CATTLE', breed TEXT, birth_date TEXT, production_status TEXT NOT NULL,
  facility_id TEXT REFERENCES assets(asset_id), avatar_key TEXT NOT NULL, notes TEXT, source_type TEXT NOT NULL DEFAULT 'SYNTHETIC', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dairy_production_records (
  dairy_record_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, animal_id TEXT REFERENCES dairy_animals(animal_id),
  production_date TEXT NOT NULL, quantity REAL NOT NULL CHECK (quantity >= 0), unit TEXT NOT NULL, processing_status TEXT NOT NULL DEFAULT 'RAW',
  saleable_quantity REAL NOT NULL DEFAULT 0 CHECK (saleable_quantity >= 0), source_type TEXT NOT NULL DEFAULT 'SYNTHETIC', notes TEXT,
  session_type TEXT NOT NULL DEFAULT 'DAILY', withheld_quantity REAL NOT NULL DEFAULT 0 CHECK (withheld_quantity >= 0), withholding_reason TEXT,
  operator TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS dairy_milk_collections (
  collection_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  collection_date TEXT NOT NULL, source_scope TEXT NOT NULL, quantity_collected REAL NOT NULL CHECK (quantity_collected > 0), unit TEXT NOT NULL,
  approved_quantity REAL NOT NULL CHECK (approved_quantity >= 0), withheld_quantity REAL NOT NULL CHECK (withheld_quantity >= 0),
  withholding_reason TEXT, storage_id TEXT REFERENCES storage_facilities(storage_id), temperature_f REAL, quality_status TEXT NOT NULL DEFAULT 'PENDING',
  processing_status TEXT NOT NULL DEFAULT 'RAW', processing_date TEXT, sell_by_date TEXT, lot_id TEXT REFERENCES inventory_lots(lot_id),
  source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED', notes TEXT, created_at TEXT NOT NULL, UNIQUE(farm_id,collection_date,source_scope)
);
CREATE TABLE IF NOT EXISTS dairy_processing_specs (
  spec_id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES products(product_id), input_unit TEXT NOT NULL DEFAULT 'liter',
  output_unit TEXT NOT NULL, input_quantity_per_output REAL NOT NULL CHECK (input_quantity_per_output > 0), shelf_life_days INTEGER NOT NULL CHECK (shelf_life_days > 0),
  processing_cost_per_output REAL NOT NULL DEFAULT 0 CHECK (processing_cost_per_output >= 0), assumption_note TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'SYNTHETIC', UNIQUE(product_id)
);
CREATE TABLE IF NOT EXISTS dairy_processing_batches (
  batch_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, input_lot_id TEXT NOT NULL REFERENCES inventory_lots(lot_id),
  product_id TEXT NOT NULL REFERENCES products(product_id), processed_at TEXT NOT NULL, input_quantity REAL NOT NULL CHECK (input_quantity > 0),
  output_quantity REAL NOT NULL CHECK (output_quantity > 0), output_unit TEXT NOT NULL, output_lot_id TEXT REFERENCES inventory_lots(lot_id),
  status TEXT NOT NULL DEFAULT 'COMPLETED', cost REAL NOT NULL DEFAULT 0 CHECK (cost >= 0), assumption_note TEXT, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED', UNIQUE(input_lot_id,batch_id)
);
CREATE TABLE IF NOT EXISTS dairy_feed_inventory (
  feed_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, feed_type TEXT NOT NULL, quantity REAL NOT NULL CHECK (quantity >= 0),
  unit TEXT NOT NULL, cost_per_unit REAL NOT NULL CHECK (cost_per_unit >= 0), dry_matter_pct REAL, received_date TEXT NOT NULL, supplier TEXT,
  source_type TEXT NOT NULL DEFAULT 'SYNTHETIC', notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dairy_feed_usage (
  usage_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, feed_id TEXT NOT NULL REFERENCES dairy_feed_inventory(feed_id),
  usage_date TEXT NOT NULL, quantity REAL NOT NULL CHECK (quantity > 0), unit TEXT NOT NULL, herd_group TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED', notes TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dairy_health_records (
  health_record_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, animal_id TEXT NOT NULL REFERENCES dairy_animals(animal_id),
  record_date TEXT NOT NULL, record_type TEXT NOT NULL, observation TEXT NOT NULL, veterinary_review_required INTEGER NOT NULL DEFAULT 0,
  milk_withdrawal_until TEXT, recorded_by TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dairy_tasks (
  task_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, category TEXT NOT NULL, priority TEXT NOT NULL,
  assigned_worker TEXT, due_date TEXT NOT NULL, animal_id TEXT REFERENCES dairy_animals(animal_id), facility_id TEXT REFERENCES assets(asset_id),
  status TEXT NOT NULL DEFAULT 'OPEN', title TEXT NOT NULL, completion_notes TEXT, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(farm_id,category,title,due_date,animal_id,facility_id)
);
CREATE TABLE IF NOT EXISTS poultry_facilities (
  facility_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  name TEXT NOT NULL, facility_type TEXT NOT NULL, acreage REAL NOT NULL DEFAULT 0 CHECK (acreage >= 0),
  hen_capacity INTEGER NOT NULL CHECK (hen_capacity >= 0), run_capacity INTEGER NOT NULL DEFAULT 0 CHECK (run_capacity >= 0),
  source_type TEXT NOT NULL DEFAULT 'SYNTHETIC', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS poultry_flocks (
  flock_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  name TEXT NOT NULL, breed TEXT NOT NULL, hens_count INTEGER NOT NULL CHECK (hens_count >= 0),
  roosters_count INTEGER NOT NULL DEFAULT 0 CHECK (roosters_count >= 0), chicks_count INTEGER NOT NULL DEFAULT 0 CHECK (chicks_count >= 0),
  hatch_date TEXT, production_status TEXT NOT NULL DEFAULT 'LAYING', facility_id TEXT REFERENCES poultry_facilities(facility_id),
  expected_laying_rate REAL NOT NULL CHECK (expected_laying_rate >= 0 AND expected_laying_rate <= 1),
  notes TEXT, source_type TEXT NOT NULL DEFAULT 'SYNTHETIC', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS poultry_flock_movements (
  movement_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  flock_id TEXT NOT NULL REFERENCES poultry_flocks(flock_id) ON DELETE CASCADE, movement_date TEXT NOT NULL,
  from_facility_id TEXT, to_facility_id TEXT, quantity INTEGER NOT NULL CHECK (quantity > 0),
  movement_type TEXT NOT NULL, notes TEXT, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS poultry_egg_collections (
  collection_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  flock_id TEXT NOT NULL REFERENCES poultry_flocks(flock_id), collection_date TEXT NOT NULL, collection_time TEXT NOT NULL,
  eggs_collected INTEGER NOT NULL CHECK (eggs_collected > 0), broken_eggs INTEGER NOT NULL DEFAULT 0 CHECK (broken_eggs >= 0),
  dirty_rejected INTEGER NOT NULL DEFAULT 0 CHECK (dirty_rejected >= 0), accepted_for_grading INTEGER NOT NULL CHECK (accepted_for_grading >= 0),
  worker TEXT NOT NULL, notes TEXT, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED', created_at TEXT NOT NULL,
  UNIQUE(flock_id, collection_date, collection_time)
);
CREATE TABLE IF NOT EXISTS poultry_egg_batches (
  batch_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  flock_id TEXT NOT NULL REFERENCES poultry_flocks(flock_id), collection_id TEXT NOT NULL UNIQUE REFERENCES poultry_egg_collections(collection_id),
  collection_date TEXT NOT NULL, total_eggs INTEGER NOT NULL CHECK (total_eggs > 0), accepted_eggs INTEGER NOT NULL CHECK (accepted_eggs >= 0),
  rejected_eggs INTEGER NOT NULL CHECK (rejected_eggs >= 0), quality_status TEXT NOT NULL DEFAULT 'UNVERIFIED', size_category TEXT,
  grading_status TEXT NOT NULL DEFAULT 'PENDING', packaging_status TEXT NOT NULL DEFAULT 'UNPACKAGED', lot_id TEXT REFERENCES inventory_lots(lot_id),
  hold_status TEXT NOT NULL DEFAULT 'AVAILABLE', source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS poultry_packaging_batches (
  packaging_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  batch_id TEXT NOT NULL REFERENCES poultry_egg_batches(batch_id), input_eggs INTEGER NOT NULL CHECK (input_eggs > 0),
  package_type TEXT NOT NULL, package_count INTEGER NOT NULL CHECK (package_count > 0), eggs_per_package INTEGER NOT NULL CHECK (eggs_per_package > 0),
  packaging_date TEXT NOT NULL, product_id TEXT NOT NULL REFERENCES products(product_id), output_lot_id TEXT REFERENCES inventory_lots(lot_id),
  storage_id TEXT, quality_status TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED', notes TEXT, created_at TEXT NOT NULL,
  UNIQUE(batch_id, package_type, packaging_date)
);
CREATE TABLE IF NOT EXISTS poultry_feed_inventory (
  feed_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, feed_type TEXT NOT NULL,
  quantity REAL NOT NULL CHECK (quantity >= 0), unit TEXT NOT NULL, cost_per_unit REAL NOT NULL CHECK (cost_per_unit >= 0),
  received_date TEXT NOT NULL, supplier TEXT, source_type TEXT NOT NULL DEFAULT 'SYNTHETIC', notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS poultry_feed_usage (
  usage_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, feed_id TEXT NOT NULL REFERENCES poultry_feed_inventory(feed_id),
  flock_id TEXT NOT NULL REFERENCES poultry_flocks(flock_id), usage_date TEXT NOT NULL, quantity REAL NOT NULL CHECK (quantity > 0),
  unit TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED', notes TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS poultry_health_records (
  health_record_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
  flock_id TEXT NOT NULL REFERENCES poultry_flocks(flock_id), event_date TEXT NOT NULL, event_type TEXT NOT NULL,
  observation TEXT NOT NULL, veterinary_review_required INTEGER NOT NULL DEFAULT 0, product_hold INTEGER NOT NULL DEFAULT 0,
  recorded_by TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS poultry_tasks (
  task_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, category TEXT NOT NULL, priority TEXT NOT NULL,
  assigned_worker TEXT, due_date TEXT NOT NULL, flock_id TEXT REFERENCES poultry_flocks(flock_id), facility_id TEXT,
  status TEXT NOT NULL DEFAULT 'OPEN', title TEXT NOT NULL, completion_notes TEXT, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(farm_id, category, title, due_date, flock_id, facility_id)
);
CREATE TABLE IF NOT EXISTS spoilage_assessments (
  assessment_id TEXT PRIMARY KEY, lot_id TEXT NOT NULL REFERENCES inventory_lots(lot_id) ON DELETE CASCADE, as_of_date TEXT NOT NULL,
  risk TEXT NOT NULL, days_to_expiry INTEGER, at_risk_quantity REAL NOT NULL, predicted_waste REAL NOT NULL,
  rescue_quantity REAL NOT NULL, gross_sales_value_at_risk REAL NOT NULL, recoverable_sales_scenario REAL,
  recommendation TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'SUGGESTED', source_type TEXT NOT NULL DEFAULT 'CALCULATED', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS buyers (
  buyer_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, business_name TEXT NOT NULL,
  category TEXT NOT NULL, street_address TEXT, latitude REAL, longitude REAL, contact_name TEXT, contact_role TEXT,
  email TEXT, phone TEXT, contact_verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED', delivery_preferences TEXT,
  minimum_order_quantity REAL NOT NULL DEFAULT 0 CHECK (minimum_order_quantity >= 0), customer_status TEXT NOT NULL DEFAULT 'PROSPECT',
  last_contacted_date TEXT, notes TEXT, source_type TEXT NOT NULL DEFAULT 'SYNTHETIC', last_verified_at TEXT, archived INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS buyer_preferences (
  preference_id TEXT PRIMARY KEY, buyer_id TEXT NOT NULL REFERENCES buyers(buyer_id) ON DELETE CASCADE, product_id TEXT NOT NULL REFERENCES products(product_id),
  min_quantity REAL NOT NULL DEFAULT 0 CHECK (min_quantity >= 0), max_quantity REAL, min_price REAL, max_price REAL, preferred_grade TEXT, delivery_days TEXT, source_type TEXT NOT NULL DEFAULT 'SYNTHETIC', UNIQUE(buyer_id,product_id)
);
CREATE TABLE IF NOT EXISTS outreach_suppressions (
  suppression_id TEXT PRIMARY KEY, buyer_id TEXT NOT NULL REFERENCES buyers(buyer_id) ON DELETE CASCADE, reason TEXT NOT NULL, suppressed_at TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED'
);
CREATE TABLE IF NOT EXISTS sales_activities (
  activity_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, buyer_id TEXT REFERENCES buyers(buyer_id), opportunity_id TEXT,
  activity_type TEXT NOT NULL, activity_date TEXT NOT NULL, summary TEXT NOT NULL, next_action TEXT, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED'
);
CREATE TABLE IF NOT EXISTS buyer_opportunities (
  opportunity_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, buyer_id TEXT NOT NULL REFERENCES buyers(buyer_id),
  stage TEXT NOT NULL, estimated_value REAL NOT NULL DEFAULT 0 CHECK (estimated_value >= 0), confirmed_value REAL NOT NULL DEFAULT 0 CHECK (confirmed_value >= 0), expected_close_date TEXT,
  owner_notes TEXT, next_action TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE TABLE IF NOT EXISTS wholesale_offers (
  offer_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, buyer_id TEXT NOT NULL REFERENCES buyers(buyer_id),
  proposed_delivery_date TEXT NOT NULL, expiration_date TEXT, payment_terms TEXT, delivery_terms TEXT, notes TEXT, total_value REAL NOT NULL CHECK (total_value >= 0),
  status TEXT NOT NULL DEFAULT 'DRAFT', source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS offer_line_items (
  offer_line_id TEXT PRIMARY KEY, offer_id TEXT NOT NULL REFERENCES wholesale_offers(offer_id) ON DELETE CASCADE, product_id TEXT NOT NULL REFERENCES products(product_id),
  lot_id TEXT REFERENCES inventory_lots(lot_id), quantity REAL NOT NULL CHECK (quantity > 0), unit TEXT NOT NULL, quality_grade TEXT, unit_price REAL NOT NULL CHECK (unit_price >= 0), line_total REAL NOT NULL CHECK (line_total >= 0), price_source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS email_drafts (
  draft_id TEXT PRIMARY KEY, offer_id TEXT NOT NULL REFERENCES wholesale_offers(offer_id) ON DELETE CASCADE, recipient_email TEXT, recipient_name TEXT,
  subject TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'DRAFT', exported_at TEXT, approved_at TEXT, source_type TEXT NOT NULL DEFAULT 'DETERMINISTIC_TEMPLATE', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS customer_orders (
  order_id TEXT PRIMARY KEY, farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE, buyer_id TEXT NOT NULL REFERENCES buyers(buyer_id), offer_id TEXT REFERENCES wholesale_offers(offer_id),
  order_date TEXT NOT NULL, delivery_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'CONFIRMED', total_value REAL NOT NULL CHECK (total_value >= 0), buyer_confirmation_reference TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'OWNER_ENTERED'
);
CREATE TABLE IF NOT EXISTS order_line_items (
  order_line_id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES customer_orders(order_id) ON DELETE CASCADE, product_id TEXT NOT NULL REFERENCES products(product_id), lot_id TEXT NOT NULL REFERENCES inventory_lots(lot_id),
  reservation_id TEXT NOT NULL REFERENCES inventory_reservations(reservation_id), quantity REAL NOT NULL CHECK (quantity > 0), unit TEXT NOT NULL, unit_price REAL NOT NULL CHECK (unit_price >= 0), line_total REAL NOT NULL CHECK (line_total >= 0)
);
CREATE TABLE IF NOT EXISTS agent_runs (
  run_id TEXT PRIMARY KEY, user_request TEXT NOT NULL, provider TEXT, model TEXT, status TEXT NOT NULL,
  started_at TEXT NOT NULL, completed_at TEXT, agents_json TEXT NOT NULL DEFAULT '[]', final_response TEXT,
  warnings_json TEXT NOT NULL DEFAULT '[]', approval_required INTEGER NOT NULL DEFAULT 0, source_type TEXT NOT NULL DEFAULT 'CALCULATED'
);
CREATE TABLE IF NOT EXISTS agent_calls (
  call_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES agent_runs(run_id) ON DELETE CASCADE, agent_id TEXT NOT NULL,
  call_type TEXT NOT NULL, tool_name TEXT, started_at TEXT NOT NULL, completed_at TEXT, latency_ms REAL,
  input_tokens INTEGER, cached_input_tokens INTEGER, output_tokens INTEGER, reasoning_tokens INTEGER, total_tokens INTEGER,
  provider TEXT, model TEXT, status TEXT NOT NULL, error_message TEXT, input_summary TEXT, output_summary TEXT, retry_count INTEGER NOT NULL DEFAULT 0,
  cost_status TEXT NOT NULL DEFAULT 'UNAVAILABLE'
);
CREATE TABLE IF NOT EXISTS agent_tool_events (
  event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES agent_runs(run_id) ON DELETE CASCADE, agent_id TEXT NOT NULL,
  tool_name TEXT NOT NULL, arguments_json TEXT NOT NULL, output_json TEXT, status TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT, error_message TEXT
);
CREATE TABLE IF NOT EXISTS token_price_table (
  price_id TEXT PRIMARY KEY, provider TEXT NOT NULL, model TEXT NOT NULL, input_per_million REAL, cached_input_per_million REAL,
  output_per_million REAL, currency TEXT NOT NULL DEFAULT 'USD', effective_date TEXT NOT NULL, official_reference TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'VERIFIED'
);
CREATE INDEX IF NOT EXISTS idx_assets_farm ON assets(farm_id);
CREATE INDEX IF NOT EXISTS idx_plans_asset ON production_plans(asset_id);
CREATE INDEX IF NOT EXISTS idx_weather_farm ON weather_snapshots(farm_id, retrieved_at);
CREATE INDEX IF NOT EXISTS idx_missions_status ON farm_missions(farm_id, status);
CREATE INDEX IF NOT EXISTS idx_financial_date ON financial_transactions(farm_id, transaction_date, classification);
CREATE INDEX IF NOT EXISTS idx_financial_category ON financial_transactions(farm_id, category, transaction_type);
CREATE INDEX IF NOT EXISTS idx_budget_period ON budgets(farm_id, period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_market_product_date ON market_observations(product_id, observation_date);
CREATE INDEX IF NOT EXISTS idx_pricing_product ON pricing_recommendations(product_id, created_at);
CREATE INDEX IF NOT EXISTS idx_approved_product_date ON approved_prices(product_id, effective_start);
CREATE INDEX IF NOT EXISTS idx_inventory_lot_product ON inventory_lots(farm_id, product_id, lot_status);
CREATE INDEX IF NOT EXISTS idx_inventory_movement_lot ON inventory_movements(lot_id, movement_at);
CREATE INDEX IF NOT EXISTS idx_inventory_reservation_lot ON inventory_reservations(lot_id, status);
CREATE INDEX IF NOT EXISTS idx_dairy_record_date ON dairy_production_records(farm_id, production_date);
CREATE INDEX IF NOT EXISTS idx_dairy_collection_date ON dairy_milk_collections(farm_id, collection_date);
CREATE INDEX IF NOT EXISTS idx_dairy_processing_input ON dairy_processing_batches(input_lot_id);
CREATE INDEX IF NOT EXISTS idx_dairy_feed_usage_date ON dairy_feed_usage(farm_id, usage_date);
CREATE INDEX IF NOT EXISTS idx_dairy_health_animal ON dairy_health_records(animal_id, record_date);
CREATE INDEX IF NOT EXISTS idx_dairy_tasks_due ON dairy_tasks(farm_id, status, due_date);
CREATE INDEX IF NOT EXISTS idx_poultry_collections_date ON poultry_egg_collections(farm_id, collection_date);
CREATE INDEX IF NOT EXISTS idx_poultry_batches_date ON poultry_egg_batches(farm_id, collection_date);
CREATE INDEX IF NOT EXISTS idx_poultry_tasks_due ON poultry_tasks(farm_id, status, due_date);
CREATE INDEX IF NOT EXISTS idx_spoilage_lot_date ON spoilage_assessments(lot_id, as_of_date);
CREATE INDEX IF NOT EXISTS idx_buyers_farm_status ON buyers(farm_id, customer_status, archived);
CREATE INDEX IF NOT EXISTS idx_buyer_preferences_product ON buyer_preferences(product_id, buyer_id);
CREATE INDEX IF NOT EXISTS idx_sales_opportunity_stage ON buyer_opportunities(farm_id, stage);
CREATE INDEX IF NOT EXISTS idx_offer_buyer_status ON wholesale_offers(buyer_id, status);
CREATE INDEX IF NOT EXISTS idx_orders_status ON customer_orders(farm_id, status);
CREATE INDEX IF NOT EXISTS idx_agent_calls_run ON agent_calls(run_id, started_at);
CREATE INDEX IF NOT EXISTS idx_agent_events_run ON agent_tool_events(run_id, started_at);
"""


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        existing = {row[1] for row in conn.execute("PRAGMA table_info(farms)").fetchall()}
        for column, definition in {
            "latitude": "REAL", "longitude": "REAL", "timezone": "TEXT DEFAULT 'America/New_York'"
        }.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE farms ADD COLUMN {column} {definition}")
        existing = {row[1] for row in conn.execute("PRAGMA table_info(crops)").fetchall()}
        crop_columns = {
            "category": "TEXT DEFAULT 'VEGETABLE'", "planting_window_start": "TEXT", "planting_window_end": "TEXT",
            "harvest_window_start": "TEXT", "harvest_window_end": "TEXT", "maturity_days": "INTEGER DEFAULT 60",
            "minimum_temperature_f": "REAL DEFAULT 40", "preferred_temperature_min_f": "REAL DEFAULT 55",
            "preferred_temperature_max_f": "REAL DEFAULT 85", "frost_tolerance_f": "REAL DEFAULT 32",
            "heat_sensitivity_f": "REAL DEFAULT 95", "water_requirement_in_week": "REAL DEFAULT 1",
            "yield_per_acre": "REAL DEFAULT 1000", "growth_stage": "TEXT DEFAULT 'GROWING'",
            "production_status": "TEXT DEFAULT 'ACTIVE'", "agronomic_source": "TEXT DEFAULT 'Configurable demonstration assumption'"
        }
        for column, definition in crop_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE crops ADD COLUMN {column} {definition}")
        conn.execute("UPDATE farms SET latitude=41.3083, longitude=-72.9279, timezone='America/New_York', location=CASE WHEN location='Connecticut, USA' THEN 'New Haven, Connecticut, USA' ELSE location END WHERE latitude IS NULL OR (latitude=41.60 AND longitude=-72.70)")
        crop_specs = {
            "Tomatoes": ("FRUIT", "04-15", "06-15", "07-15", "10-01", 80, 50, 65, 85, 32, 90, 1.25, 12000, "FRUITING", "ACTIVE"),
            "Lettuce": ("LEAFY_GREEN", "03-15", "09-15", "05-01", "10-31", 45, 35, 50, 72, 28, 80, 1.0, 9000, "GROWING", "ACTIVE"),
            "Spinach": ("LEAFY_GREEN", "03-01", "09-15", "04-01", "10-15", 40, 30, 45, 68, 20, 75, 0.9, 7000, "HARVESTED", "ACTIVE"),
            "Carrots": ("ROOT", "03-15", "07-15", "06-15", "11-15", 70, 40, 55, 75, 28, 85, 1.0, 14000, "GROWING", "ACTIVE"),
            "Potatoes": ("ROOT", "04-01", "06-01", "07-15", "10-15", 90, 40, 55, 75, 30, 85, 1.1, 13000, "GROWING", "ACTIVE"),
            "Strawberries": ("FRUIT", "03-15", "05-15", "06-01", "07-15", 120, 35, 55, 80, 28, 85, 1.2, 9000, "FRUITING", "ACTIVE"),
            "Sweet Corn": ("GRAIN", "05-01", "06-30", "07-15", "09-30", 75, 50, 60, 85, 32, 95, 1.25, 11000, "GROWING", "ACTIVE"),
            "Cucumbers": ("FRUIT", "05-01", "06-30", "07-01", "09-15", 55, 55, 65, 85, 35, 95, 1.3, 12000, "GROWING", "ACTIVE"),
        }
        for name, spec in crop_specs.items():
            conn.execute("""UPDATE crops SET category=?, planting_window_start=?, planting_window_end=?, harvest_window_start=?, harvest_window_end=?, maturity_days=?, minimum_temperature_f=?, preferred_temperature_min_f=?, preferred_temperature_max_f=?, frost_tolerance_f=?, heat_sensitivity_f=?, water_requirement_in_week=?, yield_per_acre=?, growth_stage=?, production_status=?, agronomic_source=? WHERE name=?""", (*spec, "Northeast U.S. configurable demonstration assumption; verify locally before operational use.", name))
        existing = {row[1] for row in conn.execute("PRAGMA table_info(dairy_animals)").fetchall()}
        animal_columns = {
            "sex": "TEXT DEFAULT 'FEMALE'", "herd_category": "TEXT DEFAULT 'LACTATING_COW'", "acquisition_date": "TEXT",
            "acquisition_cost": "REAL", "lactation_number": "INTEGER DEFAULT 1", "days_in_milk": "INTEGER",
            "last_calving_date": "TEXT", "expected_dry_off_date": "TEXT", "archived": "INTEGER NOT NULL DEFAULT 0"
        }
        for column, definition in animal_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE dairy_animals ADD COLUMN {column} {definition}")
        existing = {row[1] for row in conn.execute("PRAGMA table_info(dairy_production_records)").fetchall()}
        production_columns = {
            "session_type": "TEXT NOT NULL DEFAULT 'DAILY'", "withheld_quantity": "REAL NOT NULL DEFAULT 0",
            "withholding_reason": "TEXT", "operator": "TEXT", "created_at": "TEXT", "updated_at": "TEXT"
        }
        for column, definition in production_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE dairy_production_records ADD COLUMN {column} {definition}")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_dairy_session_unique ON dairy_production_records(animal_id, production_date, session_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dairy_record_animal_date ON dairy_production_records(animal_id, production_date, session_type)")
        conn.execute("UPDATE dairy_animals SET herd_category=CASE WHEN production_status='MILKING' THEN 'LACTATING_COW' WHEN production_status='DRY' THEN 'DRY_COW' ELSE COALESCE(herd_category,'OTHER') END WHERE herd_category IS NULL OR herd_category=''")
        conn.execute("UPDATE dairy_animals SET herd_category='DRY_COW' WHERE production_status='DRY' AND herd_category='LACTATING_COW'")
        conn.execute("UPDATE dairy_production_records SET created_at=COALESCE(created_at,datetime('now')), updated_at=COALESCE(updated_at,datetime('now'))")


def seed_database() -> None:
    initialize_database()
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        if conn.execute("SELECT 1 FROM farms LIMIT 1").fetchone():
            seed_financial_data(conn, now)
            seed_pricing_data(conn, now)
            seed_inventory_data(conn, now)
            seed_sales_data(conn, now)
            seed_poultry_data(conn, now)
            return
        conn.execute("INSERT INTO farms (farm_id,name,location,acreage,farm_type,source_type,created_at,updated_at,latitude,longitude,timezone) VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("farm-green-valley", "Green Valley Farm", "New Haven, Connecticut, USA", 20.0, "Mixed crop and dairy", "SYNTHETIC", now, now, 41.3083, -72.9279, "America/New_York"))
        assets = [
            ("plot-tomato", "PLOT", "Tomato Field", 2.0, "field-tomato"), ("plot-lettuce", "PLOT", "Lettuce Field", 1.0, "field-lettuce"),
            ("plot-spinach", "PLOT", "Spinach Field", 0.75, "field-spinach"), ("plot-carrots", "PLOT", "Carrot Field", 1.25, "field-carrots"),
            ("plot-potatoes", "PLOT", "Potato Field", 2.0, "field-potatoes"), ("plot-strawberries", "PLOT", "Strawberry Patch", 0.5, "field-strawberries"),
            ("plot-corn", "PLOT", "Sweet Corn Field", 2.0, "field-corn"), ("plot-cucumbers", "PLOT", "Cucumber Field", 1.5, "field-cucumbers"),
            ("facility-greenhouse", "GREENHOUSE", "North Greenhouse", 0.5, "greenhouse"), ("facility-barn", "BARN", "Dairy Barn", 0.0, "barn"),
            ("facility-storage", "STORAGE", "Cold Storage", 0.0, "storage"), ("facility-shed", "EQUIPMENT", "Equipment Shed", 0.0, "shed"),
            ("facility-coop", "POULTRY_COOP", "Chicken Coop", 0.25, "coop"), ("facility-run", "POULTRY_RUN", "Enclosed Chicken Run", 0.25, "chicken-run"),
        ]
        for aid, typ, name, acres, ref in assets:
            conn.execute("INSERT INTO assets VALUES (?,?,?,?,?,?,?,?)", (aid, "farm-green-valley", typ, name, acres, ref, "ACTIVE", "SYNTHETIC"))
        crops = [("crop-tomatoes", "Tomatoes"), ("crop-lettuce", "Lettuce"), ("crop-spinach", "Spinach"), ("crop-carrots", "Carrots"), ("crop-potatoes", "Potatoes"), ("crop-strawberries", "Strawberries"), ("crop-corn", "Sweet Corn"), ("crop-cucumbers", "Cucumbers")]
        for cid, name in crops:
            conn.execute("INSERT INTO crops (crop_id,name,variety,source_type) VALUES (?,?,?,?)", (cid, name, "Synthetic demo variety", "SYNTHETIC"))
        enrich_crop_rows(conn)
        today = date.today()
        plans = [
            ("plan-tomato", "plot-tomato", "crop-tomatoes", -70, 7, 2400, None, "GROWING", 4800, 8640),
            ("plan-lettuce", "plot-lettuce", "crop-lettuce", -35, 10, 900, 850, "GROWING", 1300, 2700),
            ("plan-spinach", "plot-spinach", "crop-spinach", -45, 4, 650, 600, "HARVESTED", 900, 1800),
            ("plan-carrots", "plot-carrots", "crop-carrots", -60, 45, 1400, None, "GROWING", 1700, 3500),
            ("plan-potatoes", "plot-potatoes", "crop-potatoes", -90, 50, 2600, None, "GROWING", 3000, 5200),
            ("plan-strawberries", "plot-strawberries", "crop-strawberries", -50, 18, 500, 460, "GROWING", 2100, 3900),
            ("plan-corn", "plot-corn", "crop-corn", -55, 30, 2200, None, "GROWING", 2400, 4400),
            ("plan-cucumbers", "plot-cucumbers", "crop-cucumbers", -42, 14, 1500, None, "GROWING", 1900, 4000),
        ]
        for pid, aid, cid, plant_offset, harvest_offset, expected, actual, status, cost, revenue in plans:
            conn.execute("INSERT INTO production_plans VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (pid, "farm-green-valley", aid, cid, (today.replace(day=1)).isoformat(), (today.fromordinal(today.toordinal()+harvest_offset)).isoformat(), expected, actual, status, cost, revenue, "SYNTHETIC"))
        conn.execute("INSERT INTO products VALUES (?,?,?,?,?)", ("product-milk", "Whole Milk", "DAIRY", "liter", "SYNTHETIC"))
        for pid, name, category in [("product-tomato", "Tomatoes", "CROP"), ("product-lettuce", "Lettuce", "CROP"), ("product-spinach", "Spinach", "CROP"), ("product-carrot", "Carrots", "CROP"), ("product-potato", "Potatoes", "CROP"), ("product-strawberry", "Strawberries", "CROP"), ("product-corn", "Sweet Corn", "CROP"), ("product-cucumber", "Cucumbers", "CROP")]:
            conn.execute("INSERT INTO products VALUES (?,?,?,?,?)", (pid, name, category, "lb", "SYNTHETIC"))
        conn.execute("INSERT INTO dairy_summary VALUES (?,?,?,?,?,?,?)", ("dairy-green-valley", "farm-green-valley", 12, 10, 185.0, "product-milk", "SYNTHETIC"))
        for i, (cat, amount) in enumerate([("Seed and transplants", 1800), ("Fertilizer", 2400), ("Labor", 7200), ("Equipment", 1600), ("Packaging", 900), ("Feed", 3100), ("Veterinary", 850)], 1):
            conn.execute("INSERT INTO expenses VALUES (?,?,?,?,?,?)", (f"expense-{i}", "farm-green-valley", cat, amount, today.isoformat(), "SYNTHETIC"))
        activities = [("Tomato Field", "Trellis inspection completed"), ("Dairy Barn", "Morning milking recorded: 185 L"), ("Cold Storage", "Storage temperature check logged"), ("Lettuce Field", "Harvest lot quality review")]
        for i, (title, detail) in enumerate(activities, 1):
            conn.execute("INSERT INTO activities VALUES (?,?,?,?,?,?)", (f"activity-{i}", "farm-green-valley", today.isoformat(), title, detail, "SYNTHETIC"))
        seed_financial_data(conn, now)
        seed_pricing_data(conn, now)
        seed_inventory_data(conn, now)
        seed_sales_data(conn, now)
        seed_poultry_data(conn, now)


def seed_financial_data(conn: sqlite3.Connection, now: str) -> None:
    """Seed consistent synthetic finance records once for clean and upgraded databases."""
    if conn.execute("SELECT 1 FROM financial_transactions LIMIT 1").fetchone():
        return
    farm_id = "farm-green-valley"
    months = [(date.today().replace(day=1) - __import__('datetime').timedelta(days=30*i)).replace(day=1) for i in range(12)]
    product_revenue = [("product-tomato", "Produce sales", 4200), ("product-lettuce", "Produce sales", 2100), ("product-strawberry", "Produce sales", 2800), ("product-milk", "Dairy product sales", 3600)]
    for i, month in enumerate(reversed(months), 1):
        month_text = month.isoformat()
        for j, (product_id, category, base) in enumerate(product_revenue):
            amount = round(base * (0.78 + (i % 5) * 0.06), 2)
            conn.execute("INSERT OR IGNORE INTO financial_transactions (transaction_id,farm_id,transaction_date,transaction_type,category,description,amount,product_id,vendor_customer,classification,cash_accrual,source_note,source_type,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (f"txn-rev-{i}-{j}", farm_id, month_text, "REVENUE", category, f"Synthetic {category.lower()} — {month.strftime('%b %Y')}", amount, product_id, "Green Valley Farm demo customer", "ACTUAL", "CASH", "Synthetic demonstration revenue; not observed market data.", "SYNTHETIC", now))
        expenses = [("Labor", 3400), ("Feed", 1450), ("Fertilizer", 900), ("Utilities", 620), ("Packaging", 420), ("Transportation", 360), ("Insurance", 220)]
        for j, (category, base) in enumerate(expenses):
            amount = round(base * (0.9 + (i % 4) * 0.05), 2)
            product_id = "product-milk" if category == "Feed" else None
            conn.execute("INSERT OR IGNORE INTO financial_transactions (transaction_id,farm_id,transaction_date,transaction_type,category,description,amount,product_id,vendor_customer,classification,cash_accrual,source_note,source_type,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (f"txn-exp-{i}-{j}", farm_id, month_text, "EXPENSE", category, f"Synthetic {category.lower()} — {month.strftime('%b %Y')}", amount, product_id, "Synthetic demo vendor", "ACTUAL", "CASH", "Synthetic demonstration expense.", "SYNTHETIC", now))
    for i in range(12):
        month = (date.today().replace(day=1) - __import__('datetime').timedelta(days=30*i)).replace(day=1)
        end = (month.replace(day=28) + __import__('datetime').timedelta(days=4)).replace(day=1) - __import__('datetime').timedelta(days=1)
        for category, amount in [("Labor", 3600), ("Feed", 1500), ("Utilities", 650), ("Produce sales", 10000), ("Dairy product sales", 3800)]:
            budget_type = "REVENUE" if "sales" in category else "EXPENSE"
            conn.execute("INSERT OR IGNORE INTO budgets VALUES (?,?,?,?,?,?,?,?,?,?)", (f"budget-{month.isoformat()}-{category.replace(' ','-')}", farm_id, month.isoformat(), end.isoformat(), budget_type, category, amount, None, None, "SYNTHETIC"))
    conn.execute("INSERT OR IGNORE INTO cost_allocations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("allocation-overhead", farm_id, "Farm overhead", 2400, "ACREAGE", 11.0, date.today().replace(month=1, day=1).isoformat(), date.today().replace(month=12, day=31).isoformat(), None, None, "Allocated across planted crop acreage; synthetic demonstration assumption.", "SYNTHETIC"))
    conn.execute("INSERT OR IGNORE INTO capital_assets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", ("asset-tractor", farm_id, "Equipment", "Utility tractor", "2024-03-15", 48000, 10, 8000, "STRAIGHT_LINE", 2200, "facility-shed", "Synthetic capital asset for depreciation and investment examples.", "SYNTHETIC"))
    conn.execute("INSERT OR IGNORE INTO capital_assets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", ("asset-greenhouse", farm_id, "Structure", "Demonstration greenhouse", "2023-04-01", 28000, 15, 3000, "STRAIGHT_LINE", 900, "facility-greenhouse", "Synthetic capital asset.", "SYNTHETIC"))


def seed_pricing_data(conn: sqlite3.Connection, now: str) -> None:
    if conn.execute("SELECT 1 FROM pricing_configs LIMIT 1").fetchone():
        return
    configs = [
        ("product-tomato","Produce","lb",2.22,3.25,2.22,.30,2160,1200,10,3.10,1.02,1.0),
        ("product-lettuce","Produce","lb",1.45,2.45,1.45,.28,900,300,7,2.20,.95,1.0),
        ("product-spinach","Produce","lb",1.50,2.35,1.50,.28,650,120,5,2.10,.98,1.0),
        ("product-carrot","Produce","lb",1.21,1.95,1.21,.25,1400,500,21,1.80,.95,1.0),
        ("product-potato","Produce","lb",1.15,1.85,1.15,.25,2600,800,30,1.65,.98,1.0),
        ("product-strawberry","Produce","lb",4.20,6.25,4.20,.32,500,100,4,6.10,1.08,.95),
        ("product-corn","Produce","lb",1.09,1.75,1.09,.25,2200,700,7,1.60,1.03,1.0),
        ("product-cucumber","Produce","lb",1.27,2.10,1.27,.28,1500,400,10,1.95,1.0,1.0),
        ("product-milk","Dairy","liter",1.35,1.95,1.35,.25,185,185,7,1.90,1.0,1.0),
    ]
    for pid, category, unit, cost, approved, floor, margin, volume, inventory, shelf, benchmark, seasonal, supply in configs:
        conn.execute("INSERT INTO pricing_configs (product_id,product_category,unit,production_cost_per_unit,current_approved_price,recommended_price,minimum_acceptable_price,target_gross_margin,expected_volume,available_inventory,shelf_life_days,market_benchmark,seasonal_adjustment,supply_adjustment,last_price_update,source_type,confidence) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (pid,category,unit,cost,approved,approved,floor,margin,volume,inventory,shelf,benchmark,seasonal,supply,date.today().isoformat(),"SYNTHETIC","DEMO_ASSUMPTION"))
        conn.execute("INSERT INTO approved_prices VALUES (?,?,?,?,?,?,?,?,?,?)", (f"approved-{pid}",pid,approved,date.today().replace(month=1,day=1).isoformat(),None,"Farm owner (synthetic demo)",None,"Synthetic seeded approved price",now,"SYNTHETIC"))
        for month in range(1,13):
            label = "PEAK" if month in ({7,8,9} if category=="Produce" else {6,7,8}) else "SHOULDER" if month in ({5,6,10} if category=="Produce" else {4,5,9}) else "OFF_SEASON"
            factor = 1.08 if label=="PEAK" else .97 if label=="SHOULDER" else 1.03
            availability = 1.15 if label=="PEAK" else .75 if label=="OFF_SEASON" else .9
            conn.execute("INSERT INTO seasonality_factors VALUES (?,?,?,?,?,?,?,?)", (f"season-{pid}-{month}",pid,month,label,factor,availability,"Synthetic Northeast seasonal configuration; not an observed market series.","SYNTHETIC"))
        conn.execute("INSERT INTO market_observations (observation_id,product_id,source,report_identifier,variety_grade,market_location,observation_date,price,quoted_unit,package_size,normalized_unit,normalized_price,conversion_method,source_url,classification,freshness_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (f"market-{pid}",pid,"Synthetic local wholesale reference","DEMO-2026", "Standard demo grade", "Connecticut synthetic reference",date.today().isoformat(),benchmark,unit,1.0,unit,benchmark,"No conversion; synthetic demonstration value.",None,"SYNTHETIC","CURRENT"))


def seed_inventory_data(conn: sqlite3.Connection, now: str) -> None:
    """Seed physical demo lots and animal profiles once on old or new databases."""
    farm_id = "farm-green-valley"
    if not conn.execute("SELECT 1 FROM storage_facilities LIMIT 1").fetchone():
        conn.execute("INSERT INTO storage_facilities VALUES (?,?,?,?,?,?,?,?,?,?)", ("storage-cold", farm_id, "facility-storage", "COLD_STORAGE", 5000, "lb_or_liter", "Produce, dairy", "Cool and dry demonstration storage", "SYNTHETIC", now))
        conn.execute("INSERT INTO storage_facilities VALUES (?,?,?,?,?,?,?,?,?,?)", ("storage-barn", farm_id, "facility-barn", "DAIRY_COOLER", 500, "liter", "Dairy", "Refrigerated dairy holding", "SYNTHETIC", now))
    if not conn.execute("SELECT 1 FROM inventory_lots LIMIT 1").fetchone():
        today = date.today()
        lots = [
            ("lot-tomato-2026-01", farm_id, "product-tomato", "plot-tomato", "CROP", today.isoformat(), 800, "lb", "A", "storage-cold", (today + __import__('datetime').timedelta(days=3)).isoformat(), "AVAILABLE", "Tomato Field / synthetic harvest receipt", "SYNTHETIC", now, now),
            ("lot-lettuce-2026-01", farm_id, "product-lettuce", "plot-lettuce", "CROP", today.isoformat(), 300, "lb", "A", "storage-cold", (today + __import__('datetime').timedelta(days=4)).isoformat(), "AVAILABLE", "Lettuce Field / synthetic harvest receipt", "SYNTHETIC", now, now),
            ("lot-milk-2026-01", farm_id, "product-milk", "facility-barn", "DAIRY", today.isoformat(), 185, "liter", "A", "storage-barn", (today + __import__('datetime').timedelta(days=6)).isoformat(), "AVAILABLE", "Dairy Barn / synthetic daily production", "SYNTHETIC", now, now),
            ("lot-spinach-2026-01", farm_id, "product-spinach", "plot-spinach", "CROP", (today - __import__('datetime').timedelta(days=8)).isoformat(), 120, "lb", "B", "storage-cold", (today - __import__('datetime').timedelta(days=2)).isoformat(), "SPOILED", "Labeled synthetic spoilage example", "SYNTHETIC", now, now),
        ]
        for lot in lots:
            conn.execute("INSERT INTO inventory_lots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", lot)
        for lot_id, qty, unit, reason in [("lot-tomato-2026-01",800,"lb","Synthetic harvest receipt"),("lot-lettuce-2026-01",300,"lb","Synthetic harvest receipt"),("lot-milk-2026-01",185,"liter","Synthetic dairy production receipt"),("lot-spinach-2026-01",120,"lb","Synthetic harvest receipt")]:
            conn.execute("INSERT INTO inventory_movements VALUES (?,?,?,?,?,?,?,?,?,?,?)", (f"movement-receipt-{lot_id}", lot_id, now, "RECEIPT", qty, unit, reason, lot_id, "Seed loader", now, "SYNTHETIC"))
        conn.execute("INSERT INTO inventory_movements VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("movement-spoilage-spinach", "lot-spinach-2026-01", now, "SPOILAGE", 120, "lb", "Synthetic spoilage example", "lot-spinach-2026-01", "Seed loader", now, "SYNTHETIC"))
        conn.execute("INSERT INTO inventory_reservations VALUES (?,?,?,?,?,?,?,?,?)", ("reservation-tomato-demo", "lot-tomato-2026-01", "Synthetic buyer reference", 150, "ACTIVE", now, (today + __import__('datetime').timedelta(days=3)).isoformat(), "Seed loader", "SYNTHETIC"))
    animals = [("animal-daisy","GV-001","Daisy","Holstein","2021-03-12","MILKING","LACTATING_COW","cow-daisy"),("animal-clover","GV-002","Clover","Jersey","2020-05-01","MILKING","LACTATING_COW","cow-clover"),("animal-maple","GV-003","Maple","Brown Swiss","2022-02-14","MILKING","LACTATING_COW","cow-maple"),("animal-buttercup","GV-004","Buttercup","Jersey","2021-08-20","MILKING","LACTATING_COW","cow-buttercup"),("animal-mochi","GV-005","Mochi","Holstein","2023-01-08","DRY","DRY_COW","cow-mochi"),("animal-hazel","GV-006","Hazel","Guernsey","2022-06-19","MILKING","LACTATING_COW","cow-hazel")]
    for animal_id, tag, name, breed, birth, status, category, avatar in animals:
        conn.execute("""INSERT OR IGNORE INTO dairy_animals
            (animal_id,farm_id,tag,name,species,breed,birth_date,production_status,facility_id,avatar_key,notes,source_type,created_at,updated_at,sex,herd_category,acquisition_date,acquisition_cost,lactation_number,days_in_milk,last_calving_date,expected_dry_off_date,archived)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (animal_id,farm_id,tag,name,"CATTLE",breed,birth,status,"facility-barn",avatar,"Health information not recorded in this demo.","SYNTHETIC",now,now,"FEMALE",category,(date.fromisoformat(birth)+__import__('datetime').timedelta(days=30)).isoformat(),1800 if category in {"LACTATING_COW","DRY_COW"} else None,2 if category in {"LACTATING_COW","DRY_COW"} else 0,120 if category=="LACTATING_COW" else None,"2026-06-15" if category=="LACTATING_COW" else None,(date.today()+__import__('datetime').timedelta(days=60)).isoformat() if category=="LACTATING_COW" else None,0))
    baseline = {"animal-daisy":40,"animal-clover":38,"animal-maple":37,"animal-buttercup":36,"animal-hazel":34}
    for animal_id, qty in baseline.items():
        for days_ago in range(30):
            production_date = date.today() - __import__('datetime').timedelta(days=days_ago)
            record_id = f"milk-history-{animal_id}-{production_date.isoformat()}"
            amount = round(qty * (1 + (days_ago % 5) * 0.01), 2)
            conn.execute("""INSERT OR IGNORE INTO dairy_production_records
                (dairy_record_id,farm_id,animal_id,production_date,quantity,unit,processing_status,saleable_quantity,source_type,notes,session_type,withheld_quantity,withholding_reason,operator,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (record_id,farm_id,animal_id,production_date.isoformat(),amount,"liter","RAW",amount,"SYNTHETIC","Synthetic 30-day milking history.","DAILY",0,None,"Seed loader",now,now))
    # Keep the current seeded daily records compatible with the richer schema.
    conn.execute("UPDATE dairy_production_records SET created_at=COALESCE(created_at,?), updated_at=COALESCE(updated_at,?), operator=COALESCE(operator,'Seed loader') WHERE source_type='SYNTHETIC'", (now,now))
    dairy_products = [("product-cream","Cream","DAIRY","liter"),("product-yogurt","Yogurt","DAIRY","liter"),("product-cheese","Cheese","DAIRY","lb"),("product-butter","Butter","DAIRY","lb")]
    for product in dairy_products:
        conn.execute("INSERT OR IGNORE INTO products VALUES (?,?,?,?,?)", (*product,"SYNTHETIC"))
    pricing = [("product-cream",.25,2.40,2.10,.30,7),("product-yogurt",.40,3.80,3.20,.30,14),("product-cheese",.12,8.50,7.00,.30,45),("product-butter",.08,6.50,5.50,.30,30)]
    for pid,cost,price,floor,margin,shelf in pricing:
        conn.execute("""INSERT OR IGNORE INTO pricing_configs
            (product_id,product_category,unit,production_cost_per_unit,current_approved_price,recommended_price,minimum_acceptable_price,target_gross_margin,expected_volume,available_inventory,shelf_life_days,market_benchmark,seasonal_adjustment,supply_adjustment,last_price_update,source_type,confidence)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (pid,"Dairy",next(p[3] for p in dairy_products if p[0]==pid),cost,price,price,floor,margin,100,0,shelf,None,1,1,date.today().isoformat(),"SYNTHETIC","DEMO_ASSUMPTION"))
    specs = [("spec-cream","product-cream","liter", "liter",4.0,7,.35),("spec-yogurt","product-yogurt","liter", "liter",1.1,14,.55),("spec-cheese","product-cheese","liter", "lb",10.0,45,1.10),("spec-butter","product-butter","liter", "lb",20.0,30,.85)]
    for spec in specs:
        conn.execute("INSERT OR IGNORE INTO dairy_processing_specs VALUES (?,?,?,?,?,?,?,?,?)", (*spec,"Synthetic processing-yield assumption; verify with the operator." ,"SYNTHETIC"))
    feeds = [("feed-hay","Hay",900,"lb",.18,.85),("feed-silage","Corn silage",1200,"lb",.12,.35),("feed-grain","Grain mix",500,"lb",.30,.88),("feed-mineral","Mineral supplement",80,"lb",.65,.98)]
    for feed_id,feed_type,quantity,unit,cost,dm in feeds:
        conn.execute("""INSERT OR IGNORE INTO dairy_feed_inventory
            (feed_id,farm_id,feed_type,quantity,unit,cost_per_unit,dry_matter_pct,received_date,supplier,source_type,notes,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (feed_id,farm_id,feed_type,quantity,unit,cost,dm,date.today().isoformat(),"Synthetic feed supplier","SYNTHETIC","Synthetic opening feed inventory.",now,now))
    for days_ago in range(7):
        task_date = date.today() + __import__('datetime').timedelta(days=days_ago)
        conn.execute("""INSERT OR IGNORE INTO dairy_tasks
            (task_id,farm_id,category,priority,assigned_worker,due_date,animal_id,facility_id,status,title,completion_notes,source_type,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (f"task-milking-{task_date.isoformat()}",farm_id,"MILKING","HIGH","Dairy team",task_date.isoformat(),None,"facility-barn","OPEN","Record daily milking","","SYNTHETIC",now,now))
    # Keep the seeded tomato example usable for the end-to-end demo while
    # never changing owner-entered inventory.
    conn.execute("UPDATE inventory_lots SET sell_by_date=? WHERE lot_id='lot-tomato-2026-01' AND source_type='SYNTHETIC' AND sell_by_date<=?", ((date.today()+__import__('datetime').timedelta(days=3)).isoformat(), date.today().isoformat()))


def seed_poultry_data(conn: sqlite3.Connection, now: str) -> None:
    """Seed an idempotent, explicitly synthetic 40-hen laying operation."""
    farm_id = "farm-green-valley"
    today = date.today()
    # Facility records are additive and share the farm map's asset records.
    for asset_id, asset_type, name, acreage, ref in [
        ("facility-coop", "POULTRY_COOP", "Chicken Coop", 0.25, "coop"),
        ("facility-run", "POULTRY_RUN", "Enclosed Chicken Run", 0.25, "chicken-run"),
    ]:
        conn.execute("INSERT OR IGNORE INTO assets VALUES (?,?,?,?,?,?,?,?)", (asset_id, farm_id, asset_type, name, acreage, ref, "ACTIVE", "SYNTHETIC"))
    conn.execute("INSERT OR IGNORE INTO poultry_facilities VALUES (?,?,?,?,?,?,?,?,?)", ("poultry-coop", farm_id, "Green Valley Henhouse", "COOP", 0.25, 40, 50, "SYNTHETIC", now))
    conn.execute("INSERT OR IGNORE INTO poultry_facilities VALUES (?,?,?,?,?,?,?,?,?)", ("poultry-run", farm_id, "Enclosed Outdoor Run", "RUN", 0.25, 40, 60, "SYNTHETIC", now))
    flocks = [
        ("flock-brown", "Brown Layer Flock", "Rhode Island Red", 20, 0, 0, "2024-03-15", "LAYING", 0.82, "Synthetic laying-hen group; no rooster required for table eggs."),
        ("flock-white", "White Layer Flock", "White Leghorn", 12, 0, 0, "2024-05-10", "LAYING", 0.86, "Synthetic laying-hen group; daylight and age effects are not measured."),
        ("flock-speckled", "Speckled Layer Flock", "Plymouth Rock", 8, 1, 4, "2025-04-20", "LAYING", 0.76, "Synthetic mixed flock; rooster is recorded but not required for table-egg output."),
    ]
    for flock_id, name, breed, hens, roosters, chicks, hatch, status, rate, notes in flocks:
        conn.execute("""INSERT OR IGNORE INTO poultry_flocks
            (flock_id,farm_id,name,breed,hens_count,roosters_count,chicks_count,hatch_date,production_status,facility_id,expected_laying_rate,notes,source_type,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (flock_id, farm_id, name, breed, hens, roosters, chicks, hatch, status, "poultry-coop", rate, notes, "SYNTHETIC", now, now))
    # Thirty stable daily collection records; accepted eggs never exceed the 40 hens.
    flock_pattern = [("flock-brown", 16), ("flock-white", 10), ("flock-speckled", 7)]
    for days_ago in range(30):
        collection_date = today - __import__('datetime').timedelta(days=days_ago)
        total = 33 + (days_ago % 3)  # 33-35 eggs, below 40 hens per day
        broken = 1 if days_ago % 9 == 0 else 0
        dirty = 1 if days_ago % 7 == 0 else 0
        remaining = total
        for index, (flock_id, base) in enumerate(flock_pattern):
            count = base + (1 if days_ago % 4 == index else 0)
            if index == len(flock_pattern) - 1:
                count = remaining
            count = min(count, remaining)
            remaining -= count
            collection_id = f"egg-collection-{collection_date.isoformat()}-{index}"
            rejected = (broken + dirty) if index == len(flock_pattern) - 1 else 0
            accepted = max(0, count - rejected)
            conn.execute("""INSERT OR IGNORE INTO poultry_egg_collections
                (collection_id,farm_id,flock_id,collection_date,collection_time,eggs_collected,broken_eggs,dirty_rejected,accepted_for_grading,worker,notes,source_type,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (collection_id, farm_id, flock_id, collection_date.isoformat(), "AM", count, broken if index == len(flock_pattern)-1 else 0, dirty if index == len(flock_pattern)-1 else 0, accepted, "Poultry team", "Synthetic daily collection record.", "SYNTHETIC", now))
            batch_id = f"egg-batch-{collection_date.isoformat()}-{index}"
            conn.execute("""INSERT OR IGNORE INTO poultry_egg_batches
                (batch_id,farm_id,flock_id,collection_id,collection_date,total_eggs,accepted_eggs,rejected_eggs,quality_status,size_category,grading_status,packaging_status,lot_id,hold_status,source_type,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (batch_id, farm_id, flock_id, collection_id, collection_date.isoformat(), count, accepted, rejected, "UNVERIFIED", "MIXED", "PENDING", "UNPACKAGED", None, "AVAILABLE", "SYNTHETIC", now))
    # Current saleable loose eggs are a physical ledger receipt, not a forecast.
    conn.execute("INSERT OR IGNORE INTO storage_facilities VALUES (?,?,?,?,?,?,?,?,?,?)", ("storage-egg-room", farm_id, "facility-coop", "EGG_STORAGE", 1000, "egg_or_package", "Eggs", "Cool, clean demonstration storage", "SYNTHETIC", now))
    conn.execute("INSERT OR IGNORE INTO products VALUES (?,?,?,?,?)", ("product-eggs-loose", "Eggs (loose)", "POULTRY", "egg", "SYNTHETIC"))
    current_lot = "lot-eggs-loose-demo"
    if not conn.execute("SELECT 1 FROM inventory_lots WHERE lot_id=?", (current_lot,)).fetchone():
        accepted_now = 30
        sell_by = today + __import__('datetime').timedelta(days=21)
        conn.execute("INSERT INTO inventory_lots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (current_lot, farm_id, "product-eggs-loose", "facility-coop", "CROP", today.isoformat(), accepted_now, "egg", "UNVERIFIED", "storage-egg-room", sell_by.isoformat(), "AVAILABLE", "Poultry coop / synthetic current egg receipt", "SYNTHETIC", now, now))
        conn.execute("INSERT INTO inventory_movements VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("movement-receipt-eggs-demo", current_lot, now, "RECEIPT", accepted_now, "egg", "Synthetic current egg collection receipt", current_lot, "Seed loader", now, "SYNTHETIC"))
    batch = conn.execute("SELECT batch_id FROM poultry_egg_batches WHERE collection_date=? ORDER BY batch_id LIMIT 1", (today.isoformat(),)).fetchone()
    if batch:
        conn.execute("UPDATE poultry_egg_batches SET lot_id=? WHERE batch_id=? AND lot_id IS NULL", (current_lot, batch[0]))
    feed = [("poultry-feed-layer", "Layer feed", 500, "lb", 0.42), ("poultry-feed-grit", "Grit and mineral", 60, "lb", 0.28)]
    for feed_id, feed_type, quantity, unit, cost in feed:
        conn.execute("""INSERT OR IGNORE INTO poultry_feed_inventory
            (feed_id,farm_id,feed_type,quantity,unit,cost_per_unit,received_date,supplier,source_type,notes,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (feed_id, farm_id, feed_type, quantity, unit, cost, today.isoformat(), "Synthetic poultry feed supplier", "SYNTHETIC", "Illustrative feed stock; not a ration recommendation.", now, now))
    for days_ago in range(7):
        usage_date = today - __import__('datetime').timedelta(days=days_ago)
        usage_id = f"poultry-feed-usage-{usage_date.isoformat()}"
        conn.execute("""INSERT OR IGNORE INTO poultry_feed_usage
            (usage_id,farm_id,feed_id,flock_id,usage_date,quantity,unit,source_type,notes,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (usage_id, farm_id, "poultry-feed-layer", "flock-brown", usage_date.isoformat(), 18, "lb", "SYNTHETIC", "Synthetic flock feed-use record.", now))
    for task in [
        ("Collect eggs", "HIGH"), ("Refill poultry water", "HIGH"), ("Inspect nesting boxes", "MEDIUM"),
        ("Clean coop and replace bedding", "MEDIUM"), ("Inspect run fencing", "LOW"), ("Record egg grading", "MEDIUM"),
    ]:
        title, priority = task
        conn.execute("""INSERT OR IGNORE INTO poultry_tasks
            (task_id,farm_id,category,priority,assigned_worker,due_date,flock_id,facility_id,status,title,completion_notes,source_type,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", ("poultry-task-" + title.lower().replace(" ", "-"), farm_id, "POULTRY", priority, "Poultry team", today.isoformat(), None, "poultry-coop", "OPEN", title, "", "SYNTHETIC", now, now))
    # Egg products/prices are additive. Prices are explicit demo assumptions, not market observations.
    products = [
        ("product-eggs-loose", "Eggs (loose)", "POULTRY", "egg"),
        ("product-eggs-half-dozen", "Eggs (half-dozen carton)", "POULTRY", "half-dozen"),
        ("product-eggs-dozen", "Eggs (dozen carton)", "POULTRY", "dozen"),
        ("product-eggs-case", "Eggs (wholesale case)", "POULTRY", "case"),
    ]
    for product in products:
        conn.execute("INSERT OR IGNORE INTO products VALUES (?,?,?,?,?)", (*product, "SYNTHETIC"))
    prices = [
        ("product-eggs-loose", "Poultry", "egg", 0.35, 0.55, 0.35, 0.30, 40, 30, 21),
        ("product-eggs-half-dozen", "Poultry", "half-dozen", 2.20, 3.60, 2.20, 0.30, 40, 0, 21),
        ("product-eggs-dozen", "Poultry", "dozen", 4.15, 6.50, 4.15, 0.30, 40, 0, 21),
        ("product-eggs-case", "Poultry", "case", 49.80, 78.00, 49.80, 0.30, 10, 0, 21),
    ]
    for pid, category, unit, cost, approved, floor, margin, volume, inventory, shelf in prices:
        conn.execute("""INSERT OR IGNORE INTO pricing_configs
            (product_id,product_category,unit,production_cost_per_unit,current_approved_price,recommended_price,minimum_acceptable_price,target_gross_margin,expected_volume,available_inventory,shelf_life_days,market_benchmark,seasonal_adjustment,supply_adjustment,last_price_update,source_type,confidence)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (pid, category, unit, cost, approved, approved, floor, margin, volume, inventory, shelf, None, 1.0, 1.0, today.isoformat(), "SYNTHETIC", "DEMO_ASSUMPTION"))
        conn.execute("INSERT OR IGNORE INTO approved_prices VALUES (?,?,?,?,?,?,?,?,?,?)", ("approved-" + pid, pid, approved, today.replace(month=1, day=1).isoformat(), None, "Farm owner (synthetic demo)", None, "Synthetic poultry pricing assumption", now, "SYNTHETIC"))
    # Existing buyer records get an egg preference without changing their contact data.
    conn.execute("""INSERT OR IGNORE INTO buyer_preferences
        (preference_id,buyer_id,product_id,min_quantity,max_quantity,min_price,max_price,preferred_grade,delivery_days,source_type)
        VALUES (?,?,?,?,?,?,?,?,?,?)""", ("pref-greenway-eggs", "buyer-grocer-greenway", "product-eggs-dozen", 10, 100, 5.0, 8.0, "UNVERIFIED", "WED", "SYNTHETIC"))
    conn.execute("""INSERT OR IGNORE INTO buyer_preferences
        (preference_id,buyer_id,product_id,min_quantity,max_quantity,min_price,max_price,preferred_grade,delivery_days,source_type)
        VALUES (?,?,?,?,?,?,?,?,?,?)""", ("pref-harbor-eggs", "buyer-harbor-super", "product-eggs-dozen", 20, 200, 5.5, 9.0, "UNVERIFIED", "FRI", "SYNTHETIC"))
    # Poultry expenses/revenue are separate categories and product-linked for Finance rollups.
    conn.execute("""INSERT OR IGNORE INTO financial_transactions
        (transaction_id,farm_id,transaction_date,transaction_type,category,description,amount,product_id,classification,cash_accrual,source_note,source_type,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", ("txn-poultry-feed-demo", farm_id, today.isoformat(), "EXPENSE", "Poultry Feed", "Synthetic layer feed expense", 210.0, "product-eggs-dozen", "ACTUAL", "CASH", "Synthetic demonstration expense.", "SYNTHETIC", now))
    conn.execute("""INSERT OR IGNORE INTO financial_transactions
        (transaction_id,farm_id,transaction_date,transaction_type,category,description,amount,product_id,classification,cash_accrual,source_note,source_type,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", ("txn-poultry-packaging-demo", farm_id, today.isoformat(), "EXPENSE", "Poultry Packaging", "Synthetic egg-carton expense", 48.0, "product-eggs-dozen", "ACTUAL", "CASH", "Synthetic demonstration expense.", "SYNTHETIC", now))
    conn.execute("""INSERT OR IGNORE INTO financial_transactions
        (transaction_id,farm_id,transaction_date,transaction_type,category,description,amount,product_id,classification,cash_accrual,source_note,source_type,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", ("txn-poultry-sales-demo", farm_id, today.isoformat(), "REVENUE", "Poultry sales", "Synthetic egg sales example", 156.0, "product-eggs-dozen", "ACTUAL", "CASH", "Synthetic demonstration revenue; not a customer order.", "SYNTHETIC", now))


def seed_sales_data(conn: sqlite3.Connection, now: str) -> None:
    if conn.execute("SELECT 1 FROM buyers LIMIT 1").fetchone():
        return
    farm_id = "farm-green-valley"
    buyers = [
        ("buyer-grocer-greenway", "Greenway Market", "INDEPENDENT_GROCERY", "100 Market Street, Hartford CT", 41.76, -72.67, "Alex Morgan", "Produce buyer", "alex.morgan@example.com", "555-0101", "OWNER_ENTERED", "Delivery mornings; local produce", 50, "PROSPECT"),
        ("buyer-harbor-super", "Harborview Supermarket", "SUPERMARKET", "20 Harbor Road, New Haven CT", 41.31, -72.92, "Jordan Lee", "Category manager", "jordan.lee@example.com", "555-0102", "UNVERIFIED", "Weekly produce delivery", 100, "PROSPECT"),
        ("buyer-table-restaurant", "Table & Field Kitchen", "RESTAURANT", "8 Farm Lane, Middletown CT", 41.56, -72.65, "Riley Chen", "Chef-owner", "riley.chen@example.com", "555-0103", "OWNER_ENTERED", "Seasonal tomatoes and greens", 20, "QUALIFIED"),
        ("buyer-coop-river", "Riverbend Food Co-op", "FOOD_COOPERATIVE", "44 Main Street, Hartford CT", 41.77, -72.68, "Casey Patel", "Purchasing lead", "casey.patel@example.com", "555-0104", "UNVERIFIED", "Local produce; pickup preferred", 40, "PROSPECT"),
        ("buyer-hub-connect", "Connecticut Fresh Hub", "FOOD_HUB", "12 Depot Way, New Britain CT", 41.66, -72.78, "Morgan Brooks", "Hub coordinator", "morgan.brooks@example.com", "555-0105", "OWNER_ENTERED", "Mixed produce, pallet delivery", 150, "PROSPECT"),
        ("buyer-distributor-north", "Northline Produce Distribution", "WHOLESALE_DISTRIBUTOR", "60 Logistics Drive, Windsor CT", 41.85, -72.65, "Taylor Kim", "Sourcing manager", "taylor.kim@example.com", "555-0106", "UNVERIFIED", "Grade A produce", 200, "PROSPECT"),
        ("buyer-school-demo", "Elm County Schools", "INSTITUTIONAL", "1 Education Plaza, Hartford CT", 41.76, -72.68, "Sam Rivera", "Food service", "sam.rivera@example.com", "555-0107", "UNVERIFIED", "Scheduled institutional deliveries", 100, "PROSPECT"),
        ("buyer-suppressed", "Old Orchard Listing", "RESTAURANT", "Synthetic address", None, None, "Unverified Contact", "Unknown", "suppressed@example.com", None, "UNVERIFIED", "No outreach", 10, "ARCHIVED"),
    ]
    for buyer_id, name, category, address, lat, lon, contact, role, email, phone, verification, delivery, minimum, status in buyers:
        conn.execute("INSERT INTO buyers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (buyer_id,farm_id,name,category,address,lat,lon,contact,role,email,phone,verification,delivery,minimum,status,None,"Synthetic buyer record; fictional contact using example.com.","SYNTHETIC",None,0,now,now))
    conn.execute("UPDATE buyers SET archived=1 WHERE buyer_id='buyer-suppressed'")
    prefs = [("pref-greenway-tomato","buyer-grocer-greenway","product-tomato",50,300,2.5,4.0,"A","MON,WED"),("pref-greenway-lettuce","buyer-grocer-greenway","product-lettuce",50,200,1.5,3.0,"A","MON"),("pref-table-tomato","buyer-table-restaurant","product-tomato",20,100,2.0,5.0,"A","TUE,THU"),("pref-table-strawberry","buyer-table-restaurant","product-strawberry",10,50,4.0,8.0,"A","TUE"),("pref-hub-tomato","buyer-hub-connect","product-tomato",150,600,2.0,4.0,"A","FRI"),("pref-super-tomato","buyer-harbor-super","product-tomato",100,500,2.5,4.5,"A","WED"),("pref-distributor-corn","buyer-distributor-north","product-corn",200,1000,1.2,2.5,"A","THU"),("pref-coop-spinach","buyer-coop-river","product-spinach",40,200,1.5,3.5,"A","SAT"),("pref-school-carrot","buyer-school-demo","product-carrot",100,500,1.0,2.5,"A","FRI")]
    for pref in prefs: conn.execute("INSERT INTO buyer_preferences VALUES (?,?,?,?,?,?,?,?,?,?)", (*pref,"SYNTHETIC"))
    conn.execute("INSERT INTO outreach_suppressions VALUES (?,?,?,?,?)", ("suppression-old-orchard","buyer-suppressed","Synthetic opt-out fixture",now,"SYNTHETIC"))
    conn.execute("INSERT INTO buyer_opportunities VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("opportunity-greenway","farm-green-valley","buyer-grocer-greenway","PROSPECT",780,0,(date.today()+__import__('datetime').timedelta(days=14)).isoformat(),"Synthetic opportunity; not confirmed demand.","Prepare tomato availability draft",now,now,"SYNTHETIC"))


if __name__ == "__main__":
    seed_database()
    print(f"Initialized synthetic database at {DATABASE_PATH}")

