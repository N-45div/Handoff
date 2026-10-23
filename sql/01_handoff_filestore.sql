-- Register the three-week Village chat slice. Files must already sit at
-- /home/zetaris/customer-data/shared/handoff/chat_messages.jsonl inside Docker.
CREATE LIGHTNING DATABASE HANDOFF DESCRIBE BY "Village chat slices for promise investigation";

CREATE LIGHTNING FILESTORE TABLE promises FROM HANDOFF FORMAT CSV OPTIONS (
  PATH "/home/zetaris/customer-data/shared/handoff/chat_messages.csv",
  inferSchema "true",
  header "true",
  multiLine "true"
);

CREATE LIGHTNING FILESTORE TABLE cu_sessions FROM HANDOFF FORMAT CSV OPTIONS (
  PATH "/home/zetaris/customer-data/shared/handoff/cu_sessions.csv",
  inferSchema "true",
  header "true",
  multiLine "true"
);
