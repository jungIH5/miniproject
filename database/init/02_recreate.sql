SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS analysis_results;
DROP TABLE IF EXISTS tb_cb_chatbot;
DROP TABLE IF EXISTS tb_sk_diagnosis;
DROP TABLE IF EXISTS tb_cs_member;
DROP TABLE IF EXISTS tb_cs_members;
DROP TABLE IF EXISTS diagnosis_results;
DROP TABLE IF EXISTS product_click_logs;
DROP TABLE IF EXISTS sample_items;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE users (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  username TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  gender TEXT NOT NULL,
  age_group TEXT NOT NULL,
  email TEXT,
  skin_type TEXT,
  skin_concerns TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_users_username (username(191))
);

CREATE TABLE tb_cs_member (
  mbr_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  mbr_name VARCHAR(255) NOT NULL UNIQUE,
  mbr_pwd VARCHAR(255) NOT NULL,
  mbr_email VARCHAR(255) NOT NULL UNIQUE,
  birth_date VARCHAR(50),
  mbr_gender ENUM('male','female','other') DEFAULT 'other',
  mbr_status ENUM('active','inactive','deleted') DEFAULT 'active',
  last_login TIMESTAMP NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE tb_cb_chatbot (
  chat_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  mbr_id BIGINT NOT NULL,
  sender_type VARCHAR(10) CHECK (sender_type IN ('USER','BOT')),
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_chatbot_mbr_id FOREIGN KEY (mbr_id) REFERENCES tb_cs_member(mbr_id)
);

CREATE TABLE tb_sk_diagnosis (
  dgns_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  mbr_id BIGINT,
  dgns_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  color VARCHAR(100),
  color_note VARCHAR(255),
  color_rmk TEXT,
  tone VARCHAR(100),
  tone_rmk TEXT,
  bright VARCHAR(100),
  bright_rmk TEXT,
  chrome VARCHAR(100),
  chrome_rmk TEXT,
  type VARCHAR(100),
  type_score INT,
  type_rmk TEXT,
  bright_score INT,
  bright_score_rmk TEXT,
  equality_score INT,
  equality_score_rmk TEXT,
  trouble_score INT,
  trouble_score_rmk TEXT,
  texture_score INT,
  texture_score_rmk TEXT,
  moisture_score INT,
  moisture_score_rmk TEXT,
  balance_score INT,
  balance_score_rmk TEXT,
  match_color TEXT,
  unmatch_color TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_diagnosis_mbr_id FOREIGN KEY (mbr_id) REFERENCES tb_cs_member(mbr_id)
);

CREATE TABLE diagnosis_results (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  session_id VARCHAR(255) NOT NULL,
  personal_color_season VARCHAR(100),
  skin_type VARCHAR(100),
  overall_score INT DEFAULT 0,
  analysis_method VARCHAR(100) DEFAULT 'basic',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE product_click_logs (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id VARCHAR(255),
  product_name TEXT NOT NULL,
  product_link TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sample_items (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE analysis_results (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  personal_color TEXT,
  personal_color_info JSON,
  skin_result JSON,
  survey_answers JSON,
  analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_analysis_user_id FOREIGN KEY (user_id) REFERENCES users(id)
);
