-- Enable pgvector extension for semantic retrieval
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Log extension setup
DO $$
BEGIN
   RAISE NOTICE 'AgentFlow database initialization completed: vector and uuid-ossp enabled';
END $$;

