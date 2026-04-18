# Apartment Feature Hierarchy (128 Dimensions)

The 128 features have been organized into hierarchical clustering based on their real-world category to help with future optimizations, UI filters, and attribute weighting.

## 1. Property Basics & Terms
- **Core Numbers**
  - `price_normalized`
  - `area_normalized`
  - `rooms_normalized`
  - `floor_normalized`
  - `year_built_normalized`
- **Logistics & Terms**
  - `is_rent`
  - `maybe_temporary`
  - `availability_immediate`
  - `availability_flexible`
  - `price_includes_utilities`
  - `deposit_required`
  - `first_time_occupancy`
  - `sublease_allowed`
  - `commercial_allowed`

## 2. Property Type
- `is_new_building`
- `is_house`
- `is_maisonette_duplex`
- `is_attic_flat`
- `is_ground_floor`
- `is_penthouse`

## 3. Interior & Room Features
- **Layout & Design**
  - `has_high_ceilings`
  - `has_gallery_loft`
  - `layout_open_plan`
  - `layout_separated_rooms`
  - `has_smart_home`
  - `is_wheelchair_accessible`
  - `has_large_windows`
  - `is_furnished`
  - `is_unfurnished`
- **Kitchen**
  - `has_modern_kitchen`
  - `has_open_kitchen`
  - `has_dishwasher`
- **Bath & Laundry**
  - `has_multiple_bathrooms`
  - `has_bathtub`
  - `has_walk_in_shower`
  - `has_guest_toilet`
  - `has_washing_machine_in_unit`
  - `has_tumbler_in_unit`
- **Flooring & Climate**
  - `has_floor_heating`
  - `has_air_conditioning`
  - `floors_wood_parquet`
  - `floors_tile`
  - `floors_laminate`
- **Storage & Extras**
  - `has_built_in_wardrobes`
  - `has_walk_in_closet`
  - `has_cellar_storage`
  - `has_attic_storage`
  - `has_basement_hobby_room`
  - `prop_fireplace`

## 4. Exterior & Outdoor Spaces
- `prop_balcony`
- `has_terrace`
- `has_loggia`
- `prop_garden_private`
- `prop_garden_shared`
- `prop_wintergarden`

## 5. Building Amenities & Utilities
- `prop_elevator`
- `prop_parking_or_garage`
- `has_bicycle_room`
- `shares_washing_room`
- `has_playground`
- `has_swimming_pool`
- `has_sauna`
- `is_minergie_certified`
- `has_solar_panels`
- `has_heat_pump`
- `has_fiber_internet`

## 6. Atmosphere, Vibe & Condition
- **Views**
  - `view_lake`
  - `view_mountains`
  - `view_city`
  - `view_nature`
  - `orientation_south_facing`
  - `vibe_breathtaking_view`
- **Condition**
  - `condition_newly_renovated`
  - `condition_needs_renovation`
  - `condition_well_maintained`
- **Vibes**
  - `vibe_bright_light`
  - `vibe_sunny`
  - `vibe_quiet_peaceful`
  - `vibe_modern`
  - `vibe_historic_charming`
  - `style_industrial_loft`
  - `vibe_luxury_premium`
  - `vibe_extravagant`
  - `vibe_cozy`
  - `vibe_spacious`
  - `vibe_compact`
  - `vibe_family_friendly`
  - `vibe_student_budget`
  - `vibe_charming_neighborhood`

## 7. Surroundings & Location
- **Geographic Data**
  - `lat_normalized`
  - `lng_normalized`
- **Neighborhood Type**
  - `location_urban_city_center`
  - `location_suburban`
  - `location_rural`
  - `surroundings_parks`
  - `surroundings_water`
  - `surroundings_forest`
- **Mobility & Transport**
  - `commute_excellent`
  - `car_dependent`
  - `bike_friendly`
  - `pedestrian_friendly`
  - `dist_public_transport_normalized`
  - `close_to_train_station`
  - `close_to_bus_tram`
  - `close_to_highway`
  - `close_to_airport`
- **Daily Facilities**
  - `dist_shop_normalized`
  - `close_to_supermarket`
  - `close_to_shopping_mall`
  - `close_to_bakery_cafe`
  - `close_to_restaurants`
  - `close_to_fitness`
  - `close_to_hospital`
- **Education**
  - `dist_kindergarten_normalized`
  - `dist_school_1_normalized`
  - `dist_school_2_normalized`
  - `close_to_kindergarten`
  - `close_to_schools`
  - `close_to_university`

## 8. Requirements & Suitability
- **Restrictions**
  - `animal_allowed`
  - `prop_child_friendly`
  - `smokers_allowed`
  - `musicians_welcome`
- **Target Profiles**
  - `suitability_singles`
  - `suitability_couples`
  - `suitability_students`
  - `suitability_expats`
  - `seniors_preferred`
