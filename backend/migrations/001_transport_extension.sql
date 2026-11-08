-- Additive transport extension. No source-table mutations or seed records.


CREATE TABLE IF NOT EXISTS belos_transport_events (
	id VARCHAR NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	minute FLOAT NOT NULL, 
	kind VARCHAR NOT NULL, 
	trip_id VARCHAR, 
	from_vehicle_id VARCHAR, 
	to_vehicle_id VARCHAR, 
	reason VARCHAR NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE IF NOT EXISTS belos_transport_plans (
	trip_id VARCHAR NOT NULL, 
	vehicle_id VARCHAR NOT NULL, 
	sequence INTEGER NOT NULL, 
	body JSON NOT NULL, 
	PRIMARY KEY (trip_id)
)

;

CREATE INDEX IF NOT EXISTS ix_belos_transport_plans_vehicle_id ON belos_transport_plans (vehicle_id);


CREATE TABLE IF NOT EXISTS belos_transport_positions (
	id VARCHAR NOT NULL, 
	vehicle_id VARCHAR NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	minute FLOAT NOT NULL, 
	lat FLOAT NOT NULL, 
	lng FLOAT NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX IF NOT EXISTS ix_belos_transport_positions_vehicle_id ON belos_transport_positions (vehicle_id);


CREATE TABLE IF NOT EXISTS belos_transport_runtime (
	id VARCHAR NOT NULL, 
	reference_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	minute FLOAT NOT NULL, 
	wall_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	running BOOLEAN NOT NULL, 
	worker_at TIMESTAMP WITH TIME ZONE, 
	speed FLOAT NOT NULL, 
	traffic BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE IF NOT EXISTS belos_transport_vehicle_state (
	vehicle_id VARCHAR NOT NULL, 
	hold_until FLOAT NOT NULL, 
	hold_reason VARCHAR NOT NULL, 
	PRIMARY KEY (vehicle_id)
)

;
