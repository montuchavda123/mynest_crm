-- Tele CRM + Project Management PostgreSQL Schema

-- 1. Create Status ENUM for Projects
CREATE TYPE project_status AS ENUM (
    'planning', 
    'design', 
    'execution', 
    'quality_check', 
    'completed', 
    'on_hold'
);

-- 2. Create Projects Table
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id INTEGER NOT NULL REFERENCES crm_api_lead(id) ON DELETE CASCADE,
    project_name VARCHAR(255) NOT NULL,
    start_date DATE,
    end_date DATE,
    budget DECIMAL(12, 2) DEFAULT 0.00,
    status project_status DEFAULT 'planning',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Create Project Logs Table
CREATE TABLE project_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL, -- Snapshot of status at log time
    note TEXT,
    updated_by_id INTEGER REFERENCES accounts_user(id) ON DELETE SET NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Create Performance Indexes
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_lead_id ON projects(lead_id);
CREATE INDEX idx_project_logs_project_id ON project_logs(project_id);

-- 5. Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_projects_updated_at
BEFORE UPDATE ON projects
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
