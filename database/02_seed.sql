-- Know Book sample data for development and demos.
-- Every seed account password is: KnowBook123

SET NAMES utf8mb4;

INSERT INTO system_config (config_key, config_value) VALUES
    ('overdue_fee_amount', '5.00'),
    ('lost_replacement_amount', '80.00'),
    ('collection_window_days', '3');

INSERT INTO user (user_id, username, password_hash, role, reader_category) VALUES
    (1, 'librarian', 'scrypt:32768:8:1$mdI4aFAMTVCytDak$9ffd1d0fabba503d24f5ed2ccd8cc4b236646aff1d31463dddd4b3676673667f023aa292a80a59c5e075adc1aa694fa60619d9cccf4a586b74c8c7e8c2f2983f', 'librarian', NULL),
    (2, 'alice', 'scrypt:32768:8:1$s3iqmryZA54GyNo6$c53d8343dbdc96ac4c3d64769ec5b32ce4557ad3057e46e67daa7d3a3331bf8a54ed75d33416dc9daf6e6cd60a089f7a40065220f797dae567ad7397364397b2', 'reader', 'undergraduate'),
    (3, 'bob', 'scrypt:32768:8:1$mIJOVVNGgbVgk94v$526213ceed6ef3a1d14916f623411dc8ffbe481898bec61ab42442dfc7ee2bb22477b4a4ebc4e29a159df29991d8521dafb4ab0da2f49c702dbe2abcecfef6ca', 'reader', 'postgraduate'),
    (4, 'carol', 'scrypt:32768:8:1$2ngoxWQd6W2e0IJy$42ac10a802f8b54aad73f802b234608189fb5063a38e23e033a0ff646f8e3ca74a842114c99a511ee1f22014b9bb3a3ac71ea2588d73e2b0caac9fb04ea044d4', 'reader', 'teaching_staff'),
    (5, 'dave', 'scrypt:32768:8:1$dbIaypPRyA976Bpt$51c6a73a64e0ba798a7dc4748617f9d279a954d1902968dd3844685f4811f4ad549410f1a609ee0db9024474a63ed6c0463a2c394300de992b5ccf8d640c7f90', 'reader', 'undergraduate'),
    (6, 'eve', 'scrypt:32768:8:1$nmi9CiHi0hpUisXR$27591936f58c589303e5d69e5433664842333849e51c23d2e6ff7293b4c604b677bc130df04cf3c0e722cd710b136d39b79d746413b09933e57cfd5c6cf997bc', 'reader', 'undergraduate');

INSERT INTO title (title_id, isbn, title, author, category, description, has_digital_version, cover_url, created_at) VALUES
    (1, '9780132350884', 'Clean Code', 'Robert C. Martin', 'Computing',
        'A handbook of agile software craftsmanship.', 1,
        'https://covers.openlibrary.org/b/isbn/9780132350884-L.jpg', '2026-09-01 09:00:00'),
    (2, '9780262033848', 'Introduction to Algorithms', 'Thomas H. Cormen', 'Computing',
        'Comprehensive textbook of algorithms.', 0,
        'https://covers.openlibrary.org/b/isbn/9780262033848-L.jpg', '2026-09-02 09:00:00'),
    (3, '9780141439518', 'Pride and Prejudice', 'Jane Austen', 'Literature',
        'A classic novel of manners and marriage.', 1,
        'https://covers.openlibrary.org/b/isbn/9780141439518-L.jpg', '2026-09-03 09:00:00'),
    (4, '9780553380163', 'A Brief History of Time', 'Stephen Hawking', 'Science',
        'An introduction to cosmology for general readers.', 0,
        'https://covers.openlibrary.org/b/isbn/9780553380163-L.jpg', '2026-09-04 09:00:00'),
    (5, '9780078022159', 'Database System Concepts', 'Abraham Silberschatz', 'Computing',
        'Core ideas behind database management systems.', 1,
        'https://covers.openlibrary.org/b/isbn/9780078022159-L.jpg', '2026-09-05 09:00:00'),
    (6, '9780743273565', 'The Great Gatsby', 'F. Scott Fitzgerald', 'Literature',
        'A novel of wealth, love and the American dream.', 0,
        'https://covers.openlibrary.org/b/isbn/9780743273565-L.jpg', '2026-09-06 09:00:00'),
    (7, '9780134610993', 'Artificial Intelligence: A Modern Approach', 'Stuart Russell', 'Computing',
        'A standard introduction to artificial intelligence.', 1,
        'https://covers.openlibrary.org/b/isbn/9780134610993-L.jpg', '2026-10-01 09:00:00'),
    (8, '9780062316097', 'Sapiens', 'Yuval Noah Harari', 'History',
        'A brief history of humankind.', 1,
        'https://covers.openlibrary.org/b/isbn/9780062316097-L.jpg', '2026-10-20 09:00:00');

INSERT INTO copy (copy_id, title_id, barcode, status, location) VALUES
    (1,  1, 'KB-0001', 'available',    'A-01-01'),
    (2,  1, 'KB-0002', 'borrowed',     'On loan'),
    (3,  1, 'KB-0003', 'available',    'A-01-01'),
    (4,  2, 'KB-0004', 'borrowed',     'On loan'),
    (5,  2, 'KB-0005', 'reserved',     'Hold shelf'),
    (6,  2, 'KB-0006', 'borrowed',     'On loan'),
    (7,  3, 'KB-0007', 'available',    'B-02-04'),
    (8,  3, 'KB-0008', 'damaged',      'Repair room'),
    (9,  4, 'KB-0009', 'lost',         'Missing'),
    (10, 4, 'KB-0010', 'available',    'C-03-02'),
    (11, 5, 'KB-0011', 'under_repair', 'Repair room'),
    (12, 5, 'KB-0012', 'available',    'A-02-08'),
    (13, 6, 'KB-0013', 'available',    'B-01-03'),
    (14, 6, 'KB-0014', 'available',    'B-01-03'),
    (15, 7, 'KB-0015', 'borrowed',     'On loan'),
    (16, 7, 'KB-0016', 'available',    'A-03-05'),
    (17, 8, 'KB-0017', 'available',    'D-01-01');

INSERT INTO loan (loan_id, reader_id, copy_id, librarian_id, borrowed_at, due_at, returned_at, renewal_count) VALUES
    -- Alice currently borrowing Clean Code (undergraduate, 14 days).
    (1, 2, 2, 1, '2026-11-01 10:00:00', '2026-11-15 10:00:00', NULL, 0),
    -- Bob overdue on Introduction to Algorithms (postgraduate, 30 days).
    (2, 3, 4, 1, '2026-09-20 10:00:00', '2026-10-20 10:00:00', NULL, 0),
    -- Eve currently borrowing the last remaining Algorithms copy.
    (3, 6, 6, 1, '2026-10-25 11:00:00', '2026-11-08 11:00:00', NULL, 0),
    -- Carol currently borrowing AIMA (teaching staff, 60 days).
    (4, 4, 15, 1, '2026-10-20 09:30:00', '2026-12-19 09:30:00', NULL, 0),
    -- Historical returned loan with one renewal.
    (5, 2, 7, 1, '2026-08-01 14:00:00', '2026-08-29 14:00:00', '2026-08-20 16:00:00', 1),
    -- Historical lost copy: loan closed when the copy was recorded lost.
    (6, 5, 9, 1, '2026-09-01 10:00:00', '2026-09-15 10:00:00', '2026-09-18 10:00:00', 0);

INSERT INTO reservation (reservation_id, reader_id, title_id, allocated_copy_id, reserved_at, status, collect_deadline) VALUES
    -- Dave is first in the Algorithms queue and has a 3-day collection window.
    (1, 5, 2, 5, '2026-11-05 09:00:00', 'ready', '2026-11-13 17:00:00'),
    -- Alice is waiting behind Dave for the same title.
    (2, 2, 2, NULL, '2026-11-06 12:00:00', 'waiting', NULL);

INSERT INTO fee (fee_id, loan_id, amount, reason, status, created_at) VALUES
    (1, 2, 5.00, 'overdue', 'unpaid', '2026-10-21 00:00:00'),
    (2, 6, 80.00, 'lost_replacement', 'paid', '2026-09-18 10:05:00');

INSERT INTO review (review_id, user_id, title_id, rating, comment) VALUES
    (1, 2, 3, 5, 'Still one of the most readable novels in the catalogue.');

INSERT INTO notification (notification_id, user_id, reservation_id, message, created_at, is_read) VALUES
    (1, 5, 1, 'Your reserved copy of Introduction to Algorithms is ready. Please collect it by 13 November 2026.', '2026-11-10 09:05:00', 0);
