-- Know Book schema (MySQL 8 / InnoDB / utf8mb4)
-- Source of truth for tables, constraints and indexes.
-- Import order: 01_schema.sql then 02_seed.sql.

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS notification;
DROP TABLE IF EXISTS review;
DROP TABLE IF EXISTS fee;
DROP TABLE IF EXISTS reservation;
DROP TABLE IF EXISTS loan;
DROP TABLE IF EXISTS copy;
DROP TABLE IF EXISTS title;
DROP TABLE IF EXISTS user;
DROP TABLE IF EXISTS system_config;

SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------------
-- Configuration (overdue / lost replacement amounts, collection window)
-- ---------------------------------------------------------------------------
CREATE TABLE system_config (
    config_key   VARCHAR(64)  NOT NULL,
    config_value VARCHAR(255) NOT NULL,
    PRIMARY KEY (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Users
-- ---------------------------------------------------------------------------
CREATE TABLE user (
    user_id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    username         VARCHAR(50)  NOT NULL,
    password_hash    VARCHAR(255) NOT NULL,
    role             ENUM('reader', 'librarian') NOT NULL,
    reader_category  ENUM('undergraduate', 'postgraduate', 'teaching_staff') NULL,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id),
    UNIQUE KEY uk_user_username (username),
    CONSTRAINT chk_user_category CHECK (
        (role = 'reader' AND reader_category IS NOT NULL)
        OR (role = 'librarian' AND reader_category IS NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Titles (catalogue works, not physical copies)
-- ---------------------------------------------------------------------------
CREATE TABLE title (
    title_id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
    isbn                 VARCHAR(20)  NOT NULL,
    title                VARCHAR(200) NOT NULL,
    author               VARCHAR(200) NOT NULL,
    category             VARCHAR(80)  NOT NULL,
    description          TEXT         NULL,
    has_digital_version  TINYINT(1)   NOT NULL DEFAULT 0,
    cover_url            VARCHAR(500) NULL,
    created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (title_id),
    UNIQUE KEY uk_title_isbn (isbn),
    KEY idx_title_name (title),
    KEY idx_title_author (author),
    KEY idx_title_category (category),
    KEY idx_title_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Copies (inventory source of truth)
-- Available quantity is counted from copy.status, never stored on title.
-- ---------------------------------------------------------------------------
CREATE TABLE copy (
    copy_id   INT UNSIGNED NOT NULL AUTO_INCREMENT,
    title_id  INT UNSIGNED NOT NULL,
    barcode   VARCHAR(32)  NOT NULL,
    status    ENUM('available', 'borrowed', 'reserved', 'damaged', 'lost', 'under_repair') NOT NULL DEFAULT 'available',
    location  VARCHAR(80)  NULL,
    PRIMARY KEY (copy_id),
    UNIQUE KEY uk_copy_barcode (barcode),
    KEY idx_copy_title_status (title_id, status),
    CONSTRAINT fk_copy_title
        FOREIGN KEY (title_id) REFERENCES title (title_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Loans
-- Open loan: returned_at IS NULL.
-- Generated is_open lets MySQL enforce one open loan per copy.
-- ---------------------------------------------------------------------------
CREATE TABLE loan (
    loan_id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
    reader_id      INT UNSIGNED NOT NULL,
    copy_id        INT UNSIGNED NOT NULL,
    librarian_id   INT UNSIGNED NOT NULL,
    borrowed_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    due_at         DATETIME     NOT NULL,
    returned_at    DATETIME     NULL,
    renewal_count  TINYINT UNSIGNED NOT NULL DEFAULT 0,
    is_open        TINYINT GENERATED ALWAYS AS (IF(returned_at IS NULL, 1, NULL)) STORED,
    PRIMARY KEY (loan_id),
    UNIQUE KEY uk_loan_one_open_per_copy (copy_id, is_open),
    KEY idx_loan_reader_open (reader_id, returned_at),
    KEY idx_loan_copy_open (copy_id, returned_at),
    KEY idx_loan_due (due_at),
    CONSTRAINT chk_loan_renewal CHECK (renewal_count IN (0, 1)),
    CONSTRAINT chk_loan_dates CHECK (returned_at IS NULL OR returned_at >= borrowed_at),
    CONSTRAINT fk_loan_reader
        FOREIGN KEY (reader_id) REFERENCES user (user_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_loan_copy
        FOREIGN KEY (copy_id) REFERENCES copy (copy_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_loan_librarian
        FOREIGN KEY (librarian_id) REFERENCES user (user_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Reservations (queued on a title, not a specific copy until ready)
-- Queue position is calculated: same title, status=waiting,
-- ORDER BY reserved_at, reservation_id.
-- ---------------------------------------------------------------------------
CREATE TABLE reservation (
    reservation_id      INT UNSIGNED NOT NULL AUTO_INCREMENT,
    reader_id           INT UNSIGNED NOT NULL,
    title_id            INT UNSIGNED NOT NULL,
    allocated_copy_id   INT UNSIGNED NULL,
    reserved_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status              ENUM('waiting', 'ready', 'fulfilled', 'cancelled', 'expired') NOT NULL DEFAULT 'waiting',
    collect_deadline    DATETIME     NULL,
    is_open             TINYINT GENERATED ALWAYS AS (
                            IF(status IN ('waiting', 'ready'), 1, NULL)
                        ) STORED,
    PRIMARY KEY (reservation_id),
    UNIQUE KEY uk_res_one_open_per_reader_title (reader_id, title_id, is_open),
    UNIQUE KEY uk_res_one_ready_per_copy (allocated_copy_id),
    KEY idx_res_queue (title_id, status, reserved_at, reservation_id),
    KEY idx_res_reader (reader_id, status),
    CONSTRAINT fk_res_reader
        FOREIGN KEY (reader_id) REFERENCES user (user_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_res_title
        FOREIGN KEY (title_id) REFERENCES title (title_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_res_allocated_copy
        FOREIGN KEY (allocated_copy_id) REFERENCES copy (copy_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Fees (one overdue and one lost-replacement charge per loan)
-- Reader is derived from loan.reader_id, not stored here.
-- ---------------------------------------------------------------------------
CREATE TABLE fee (
    fee_id      INT UNSIGNED NOT NULL AUTO_INCREMENT,
    loan_id     INT UNSIGNED NOT NULL,
    amount      DECIMAL(8,2) NOT NULL,
    reason      ENUM('overdue', 'lost_replacement') NOT NULL,
    status      ENUM('unpaid', 'paid', 'cancelled') NOT NULL DEFAULT 'unpaid',
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (fee_id),
    UNIQUE KEY uk_fee_one_reason_per_loan (loan_id, reason),
    KEY idx_fee_status (status),
    CONSTRAINT chk_fee_amount CHECK (amount >= 0),
    CONSTRAINT fk_fee_loan
        FOREIGN KEY (loan_id) REFERENCES loan (loan_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Optional: one review per reader per title
-- ---------------------------------------------------------------------------
CREATE TABLE review (
    review_id   INT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id     INT UNSIGNED NOT NULL,
    title_id    INT UNSIGNED NOT NULL,
    rating      TINYINT UNSIGNED NOT NULL,
    comment     VARCHAR(1000) NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (review_id),
    UNIQUE KEY uk_review_user_title (user_id, title_id),
    KEY idx_review_title (title_id),
    CONSTRAINT chk_review_rating CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT fk_review_user
        FOREIGN KEY (user_id) REFERENCES user (user_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_review_title
        FOREIGN KEY (title_id) REFERENCES title (title_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Optional: collection notices
-- ---------------------------------------------------------------------------
CREATE TABLE notification (
    notification_id  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id          INT UNSIGNED NOT NULL,
    reservation_id   INT UNSIGNED NOT NULL,
    message          VARCHAR(500) NOT NULL,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_read          TINYINT(1) NOT NULL DEFAULT 0,
    PRIMARY KEY (notification_id),
    KEY idx_notification_user_read (user_id, is_read, created_at),
    CONSTRAINT fk_notification_user
        FOREIGN KEY (user_id) REFERENCES user (user_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_notification_reservation
        FOREIGN KEY (reservation_id) REFERENCES reservation (reservation_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Allocated copy must belong to the reserved title.
DELIMITER $$

CREATE TRIGGER trg_reservation_before_insert
BEFORE INSERT ON reservation
FOR EACH ROW
BEGIN
    IF NEW.status = 'ready' THEN
        IF NEW.allocated_copy_id IS NULL OR NEW.collect_deadline IS NULL THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'A ready reservation must have an allocated copy and a collection deadline';
        END IF;
    ELSEIF NEW.allocated_copy_id IS NOT NULL OR NEW.collect_deadline IS NOT NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Only a ready reservation may have an allocated copy or collection deadline';
    END IF;
    IF NEW.allocated_copy_id IS NOT NULL THEN
        IF (SELECT c.title_id FROM copy AS c WHERE c.copy_id = NEW.allocated_copy_id) <> NEW.title_id THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Allocated copy must belong to the reserved title';
        END IF;
    END IF;
END$$

CREATE TRIGGER trg_reservation_before_update
BEFORE UPDATE ON reservation
FOR EACH ROW
BEGIN
    IF NEW.status = 'ready' THEN
        IF NEW.allocated_copy_id IS NULL OR NEW.collect_deadline IS NULL THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'A ready reservation must have an allocated copy and a collection deadline';
        END IF;
    ELSEIF NEW.allocated_copy_id IS NOT NULL OR NEW.collect_deadline IS NOT NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Only a ready reservation may have an allocated copy or collection deadline';
    END IF;
    IF NEW.allocated_copy_id IS NOT NULL THEN
        IF (SELECT c.title_id FROM copy AS c WHERE c.copy_id = NEW.allocated_copy_id) <> NEW.title_id THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Allocated copy must belong to the reserved title';
        END IF;
    END IF;
END$$

DELIMITER ;
