ALTER TABLE books
ADD CONSTRAINT books_file_type_check CHECK (file_type IN ('pdf', 'epub'));
