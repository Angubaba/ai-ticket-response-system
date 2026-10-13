-- Auto-generated from app/models.py (PostgreSQL). The app also creates these tables itself on startup.

CREATE TABLE field_definitions (
	id SERIAL NOT NULL, 
	key VARCHAR(60) NOT NULL, 
	label VARCHAR(120) NOT NULL, 
	field_type VARCHAR(20) NOT NULL, 
	required BOOLEAN NOT NULL, 
	options JSON, 
	sort_order INTEGER NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_field_definitions_key ON field_definitions (key);

CREATE TABLE tickets (
	id SERIAL NOT NULL, 
	customer_name VARCHAR(120) NOT NULL, 
	subject VARCHAR(255) NOT NULL, 
	description TEXT NOT NULL, 
	category VARCHAR(60), 
	priority VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	predicted_solution TEXT, 
	ml_confidence FLOAT, 
	ai_response TEXT, 
	final_response TEXT, 
	ai_sources JSON, 
	ai_status VARCHAR(20) NOT NULL, 
	ai_error TEXT, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE ticket_field_values (
	id SERIAL NOT NULL, 
	ticket_id INTEGER NOT NULL, 
	field_id INTEGER NOT NULL, 
	value TEXT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_ticket_field UNIQUE (ticket_id, field_id), 
	FOREIGN KEY(ticket_id) REFERENCES tickets (id) ON DELETE CASCADE, 
	FOREIGN KEY(field_id) REFERENCES field_definitions (id) ON DELETE CASCADE
);

CREATE INDEX ix_ticket_field_values_field_id ON ticket_field_values (field_id);

CREATE INDEX ix_ticket_field_values_ticket_id ON ticket_field_values (ticket_id);
