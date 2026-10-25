-- Register the three-week Village slices. Files must already sit in
-- /home/zetaris/customer-data/shared/handoff/ inside the driver container.
-- Chat and turns are Parquet: Zetaris reads CSV with backslash escapes, so quoted
-- chat split into junk rows when it was CSV.
CREATE LIGHTNING DATABASE HANDOFF DESCRIBE BY "Village chat slices for promise investigation";

DROP LIGHTNING DATABASE TABLE HANDOFF.promises;

CREATE LIGHTNING FILESTORE TABLE promises FROM HANDOFF FORMAT PARQUET OPTIONS (
  PATH "/home/zetaris/customer-data/shared/handoff/chat_messages.parquet",
  inferSchema "true"
);

CREATE LIGHTNING FILESTORE TABLE cu_sessions FROM HANDOFF FORMAT CSV OPTIONS (
  PATH "/home/zetaris/customer-data/shared/handoff/cu_sessions.csv",
  inferSchema "true",
  header "true",
  multiLine "true"
);

CREATE LIGHTNING FILESTORE TABLE cu_turns FROM HANDOFF FORMAT PARQUET OPTIONS (
  PATH "/home/zetaris/customer-data/shared/handoff/cu_turns.parquet",
  inferSchema "true"
);

CREATE LIGHTNING FILESTORE TABLE memories FROM HANDOFF FORMAT PARQUET OPTIONS (
  PATH "/home/zetaris/customer-data/shared/handoff/memories.parquet",
  inferSchema "true"
);
