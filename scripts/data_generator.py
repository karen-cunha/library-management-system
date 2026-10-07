import random
from datetime import datetime, timedelta

NUM_GENRES = 10
BOOKS_PER_GENRE = 100
NUM_READERS = 100
REVIEWS_PER_READER = 2
LOANS_PER_READER = 3

def generate_sql():
    with open('scripts/populate_library.sql', 'w', encoding='utf-8') as f:

        # Generate 100 readers
        for i in range(1, NUM_READERS + 1):
            username = f'reader_{i:03d}'
            email = f'reader{i}@mail.com'

            # Insert user
            f.write(
                f"INSERT INTO users (username, email, password) "
                f"VALUES ('{username}', '{email}', 'password123');\n"
            )

            # Insert reader role
            f.write(
                f"INSERT INTO reader (user_id) "
                f"SELECT user_id FROM users WHERE username = '{username}';\n"
            )

        # Generate books
        all_isbns = []

        for genre_id in range(1, NUM_GENRES + 1):
            for b in range(1, BOOKS_PER_GENRE + 1):

                isbn = f"978-{random.randint(10,99)}-{random.randint(1000,9999)}-{genre_id}-{b}"
                all_isbns.append(isbn)

                title = f"Book Title {genre_id}-{b}"
                desc = f"A fascinating book from genre {genre_id}."
                pages = random.randint(150, 800)
                copies = random.randint(5, 20)

                reg_date = (
                    datetime.now() -
                    timedelta(days=random.randint(10, 1000))
                ).strftime('%Y-%m-%d')

                # Insert book
                f.write(
                    f"INSERT INTO books "
                    f"(isbn, book_name, book_description, pages, copies, registration_date) "
                    f"VALUES "
                    f"('{isbn}', '{title}', '{desc}', {pages}, {copies}, '{reg_date}');\n"
                )

                # Main genre
                f.write(
                    f"INSERT INTO book_genres (isbn, genre_id) "
                    f"VALUES ('{isbn}', {genre_id});\n"
                )

                # Optional second genre
                if random.random() > 0.80:
                    second_genre = random.randint(1, NUM_GENRES)

                    if second_genre != genre_id:
                        f.write(
                            f"INSERT INTO book_genres (isbn, genre_id) "
                            f"VALUES ('{isbn}', {second_genre}) "
                            f"ON CONFLICT DO NOTHING;\n"
                        )

                # Random author
                author_id = random.randint(1, 5)

                f.write(
                    f"INSERT INTO author_books (author_id, isbn) "
                    f"VALUES ({author_id}, '{isbn}');\n"
                )

        # Generate reviews
        f.write("\n-- Reviews\n")

        for i in range(1, NUM_READERS + 1):

            user_id = i + 3  # readers are from 4 to 103

            reviewed_books = random.sample(
                all_isbns,
                REVIEWS_PER_READER
            )

            for isbn in reviewed_books:

                rating = random.randint(1, 5)

                comment = (
                    f"Review from reader {user_id} for {isbn}."
                )

                rev_date = (
                    datetime.now() -
                    timedelta(days=random.randint(1, 30))
                ).strftime('%Y-%m-%d')

                f.write(
                    f"INSERT INTO reviews "
                    f"(user_id, isbn, rating, comment, review_date) "
                    f"VALUES "
                    f"({user_id}, '{isbn}', {rating}, '{comment}', '{rev_date}');\n"
                )

        # Generate loans
        f.write("\n-- Loans\n")

        for i in range(1, NUM_READERS + 1):

            user_id = i + 3  # 4-103

            loaned_books = random.sample(
                all_isbns,
                LOANS_PER_READER
            )

            for isbn in loaned_books:

                loan_date_obj = (
                    datetime.now() -
                    timedelta(days=random.randint(1, 60))
                )

                loan_date = loan_date_obj.strftime('%Y-%m-%d')

                # 70% active loans
                if random.random() < 0.70:

                    f.write(
                        f"INSERT INTO loans "
                        f"(user_id, isbn, loan_date, return_date) "
                        f"VALUES "
                        f"({user_id}, '{isbn}', '{loan_date}', NULL);\n"
                    )

                # 30% returned loans
                else:

                    return_date_obj = (
                        loan_date_obj +
                        timedelta(days=random.randint(1, 20))
                    )

                    return_date = return_date_obj.strftime('%Y-%m-%d')

                    f.write(
                        f"INSERT INTO loans "
                        f"(user_id, isbn, loan_date, return_date) "
                        f"VALUES "
                        f"({user_id}, '{isbn}', '{loan_date}', '{return_date}');\n"
                    )

if __name__ == "__main__":
    generate_sql()