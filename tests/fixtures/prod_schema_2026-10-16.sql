CREATE TABLE achievements
                            (guild_id INTEGER,
                             user_id INTEGER,
                             achievement_id TEXT,
                             earned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                             PRIMARY KEY (guild_id, user_id, achievement_id));
CREATE TABLE ai_dm_summaries
                            (user_id INTEGER PRIMARY KEY,
                             summary TEXT,
                             last_id INTEGER,
                             updated_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE ai_embeddings
                            (history_id INTEGER PRIMARY KEY,
                             user_id INTEGER,
                             text TEXT,
                             vector BLOB, is_dm INTEGER DEFAULT 0);
CREATE TABLE ai_history
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                         user_id INTEGER, 
                         guild_id INTEGER,
                         role TEXT, 
                         content TEXT, 
                         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE ai_summaries
                            (user_id INTEGER PRIMARY KEY,
                             summary TEXT,
                             last_id INTEGER,
                             updated_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE announced
                            (item_key TEXT PRIMARY KEY,
                             created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE birthdays
                            (guild_id INTEGER,
                             user_id INTEGER,
                             month INTEGER,
                             day INTEGER,
                             PRIMARY KEY (guild_id, user_id));
CREATE TABLE game_ratings
                        (game_id INTEGER,
                         user_id INTEGER,
                         guild_id INTEGER,
                         rating INTEGER CHECK(rating >= 1 AND rating <= 10),
                         PRIMARY KEY (game_id, user_id, guild_id),
                         FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE);
CREATE TABLE game_tags
                        (game_id INTEGER,
                         tag_id INTEGER,
                         PRIMARY KEY (game_id, tag_id),
                         FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
                         FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE);
CREATE TABLE games
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                             title TEXT,
                             category TEXT,
                             min_players INTEGER,
                             max_players INTEGER,
                             ideal_players INTEGER,
                             status TEXT DEFAULT 'unknown',
                             external_rating TEXT,
                             notes TEXT,
                             release_date TEXT,
                             release_state TEXT,
                             last_update TEXT,
                             store_link TEXT,
                             added_by INTEGER,
                             guild_id INTEGER,
                             created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                             UNIQUE(title, guild_id));
CREATE TABLE gifts
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, link TEXT, claimed_by INTEGER);
CREATE TABLE guild_settings
                            (guild_id INTEGER,
                             key TEXT,
                             value TEXT,
                             PRIMARY KEY (guild_id, key));
CREATE TABLE music_sessions
                            (channel_id INTEGER PRIMARY KEY,
                             guild_id INTEGER,
                             text_channel_id INTEGER,
                             current TEXT,
                             position REAL,
                             queue TEXT,
                             paused INTEGER,
                             saved_at REAL);
CREATE TABLE science_points
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                             guild_id INTEGER,
                             user_id INTEGER,
                             amount INTEGER,
                             reason TEXT,
                             award_key TEXT UNIQUE,
                             created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE tags
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                             name TEXT,
                             guild_id INTEGER,
                             created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                             UNIQUE(name, guild_id));
CREATE TABLE trivia_answers
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                             question_id INTEGER,
                             user_id INTEGER,
                             choice INTEGER,
                             correct INTEGER,
                             answered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                             UNIQUE (question_id, user_id));
CREATE TABLE trivia_questions
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                             guild_id INTEGER,
                             local_date TEXT,
                             question TEXT,
                             choices TEXT,
                             correct_index INTEGER,
                             category TEXT,
                             channel_id INTEGER,
                             message_id INTEGER,
                             closes_at TEXT,
                             closed INTEGER DEFAULT 0,
                             UNIQUE (guild_id, local_date));
CREATE TABLE user_facts
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                             user_id INTEGER,
                             fact TEXT,
                             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, is_dm INTEGER DEFAULT 0);
CREATE INDEX idx_ai_embeddings_user ON ai_embeddings (user_id);
CREATE INDEX idx_science_points_guild_user ON science_points (guild_id, user_id);
