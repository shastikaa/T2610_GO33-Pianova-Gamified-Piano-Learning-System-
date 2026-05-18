-- SQLSELECT * FROM scores ORDER BY id DESC;
SELECT * FROM scores ORDER BY id DESC;
SELECT * FROM progress ORDER BY id DESC;
SELECT
  u.id,
  u.username,
  u.role,
  COUNT(s.id) AS games_played,
  COALESCE(MAX(s.score), 0) AS best_score,
  COALESCE(SUM(s.score), 0) AS total_score
FROM users u
LEFT JOIN scores s ON s.user_id = u.id
GROUP BY u.id, u.username, u.role
ORDER BY u.id DESC;


