SELECT slice_slug, COUNT(*) AS n
FROM HANDOFF.promises
GROUP BY slice_slug;

SELECT speaker, COUNT(*) AS n
FROM HANDOFF.promises
GROUP BY speaker
ORDER BY n DESC
LIMIT 20;
