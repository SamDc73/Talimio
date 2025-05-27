-- Add UUID column to videos table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'videos' AND column_name = 'uuid') THEN
        -- Add uuid column
        ALTER TABLE videos ADD COLUMN uuid UUID DEFAULT gen_random_uuid() NOT NULL;
        
        -- Add unique constraint
        ALTER TABLE videos ADD CONSTRAINT videos_uuid_unique UNIQUE (uuid);
        
        -- Add index
        CREATE INDEX ix_videos_uuid ON videos (uuid);
        
        RAISE NOTICE 'UUID column added to videos table';
    ELSE
        RAISE NOTICE 'UUID column already exists in videos table';
    END IF;
END $$;