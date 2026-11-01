-- ===============================================================================
-- NetSpot Security - Row Level Security (RLS) Template para PostgreSQL
-- ===============================================================================
-- Objetivo: Demonstrar a blindagem contra a falha "Banco sem Tranca" (OWASP A01:2021)
-- isolando os dados de hosts, métricas e alertas em nível de linha no banco de dados
-- para operação multi-tenant / multi-empresa.
-- ===============================================================================

-- 1. Habilitar a extensão pgcrypto para geração de UUIDs opacos (mitigação de IDOR)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. Adicionar coluna tenant_id ou owner_id nas tabelas principais
ALTER TABLE hosts ADD COLUMN IF NOT EXISTS tenant_id UUID DEFAULT gen_random_uuid();
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE checks ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE snmp_metrics ADD COLUMN IF NOT EXISTS tenant_id UUID;

-- 3. Habilitar Row Level Security (RLS) em cada tabela
ALTER TABLE hosts ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE snmp_metrics ENABLE ROW LEVEL SECURITY;

-- 4. Criar políticas de isolamento de linha (Policies)
-- A sessão da aplicação define a variável: SET LOCAL app.current_tenant_id = 'uuid-do-tenant';

CREATE POLICY host_tenant_isolation_policy ON hosts
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE POLICY alert_tenant_isolation_policy ON alerts
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE POLICY checks_tenant_isolation_policy ON checks
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE POLICY incidents_tenant_isolation_policy ON incidents
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE POLICY snmp_metrics_tenant_isolation_policy ON snmp_metrics
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

-- 5. Política para superusuário de manutenção (Bypass controlado)
-- Apenas o usuário mestre do banco de dados (dba/sre) pode ignorar as políticas para rotinas globais:
ALTER TABLE hosts FORCE ROW LEVEL SECURITY;
ALTER TABLE alerts FORCE ROW LEVEL SECURITY;
ALTER TABLE checks FORCE ROW LEVEL SECURITY;
ALTER TABLE incidents FORCE ROW LEVEL SECURITY;
ALTER TABLE snmp_metrics FORCE ROW LEVEL SECURITY;
