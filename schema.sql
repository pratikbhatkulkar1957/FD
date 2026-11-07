-- FD Rates Tracker - MySQL schema (Hostinger)
--
-- banks        : list of banks we track
-- fd_rates     : latest rate for each bank + FD type + tenure + deposit slab
-- rate_history : append-only log whenever a rate value changes

CREATE TABLE IF NOT EXISTS banks (
    slug        VARCHAR(80) PRIMARY KEY,
    name        VARCHAR(160) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fd_rates (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    bank_slug       VARCHAR(80) NOT NULL,
    fd_type         ENUM('callable', 'non_callable') NOT NULL,
    tenure_label    VARCHAR(160) NOT NULL,
    tenure_min_days INT NOT NULL,
    tenure_max_days INT NOT NULL,
    deposit_slab    ENUM('<3 crore', '3 Cr < 5 Cr') NOT NULL,
    sort_order      INT NOT NULL DEFAULT 0,
    rate_percent    DECIMAL(5,2) NOT NULL,
    source_url      TEXT NULL,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_fd_rates_bank
        FOREIGN KEY (bank_slug) REFERENCES banks(slug)
        ON DELETE CASCADE,
    UNIQUE KEY uq_fd_rates_current (bank_slug, fd_type, tenure_label, deposit_slab),
    KEY idx_fd_rates_bank (bank_slug),
    KEY idx_fd_rates_lookup (fd_type, tenure_label, deposit_slab, rate_percent DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS rate_history (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    bank_slug    VARCHAR(80) NOT NULL,
    fd_type      ENUM('callable', 'non_callable') NOT NULL,
    tenure_label VARCHAR(160) NOT NULL,
    deposit_slab ENUM('<3 crore', '3 Cr < 5 Cr') NOT NULL,
    rate_percent DECIMAL(5,2) NOT NULL,
    source_url   TEXT NULL,
    changed_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_rate_history_bank
        FOREIGN KEY (bank_slug) REFERENCES banks(slug)
        ON DELETE CASCADE,
    KEY idx_rate_history_bank_time (bank_slug, changed_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
