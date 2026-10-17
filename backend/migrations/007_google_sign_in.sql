-- Google sign-in: Google-only users have no password; google_sub links a Google account.
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
ALTER TABLE users ADD COLUMN google_sub text UNIQUE;
