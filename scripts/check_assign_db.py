from app import get_db_connection

conn = get_db_connection()
if not conn:
    print('NO CONNECTION')
    exit(1)
cur = conn.cursor()
try:
    cur.execute("SELECT COUNT(*) FROM properties WHERE property_type = 'rent' AND status = 'active'")
    print('rental properties count:', cur.fetchone()[0])
except Exception as e:
    print('properties query error:', e)
try:
    cur.execute("SELECT id, title FROM properties WHERE property_type = 'rent' AND status = 'active' LIMIT 5")
    print('sample properties:', cur.fetchall())
except Exception as e:
    print('properties sample error:', e)
try:
    cur.execute("SELECT COUNT(*) FROM users WHERE role = 'user' AND (status = 'active' OR status IS NULL)")
    print('user count:', cur.fetchone()[0])
except Exception as e:
    print('users query error:', e)
try:
    cur.execute("SELECT id, email FROM users WHERE role = 'user' LIMIT 5")
    print('sample users:', cur.fetchall())
except Exception as e:
    print('users sample error:', e)
finally:
    cur.close()
    conn.close()