# Replace Documents Only After Successful Ingestion

Document Replacement keeps the existing Document current while the replacement ingests, and only supersedes it after the new Document successfully completes ingestion. This avoids removing working knowledge from the Document Library when a replacement upload is corrupt, unsupported at processing time, or fails during embedding, at the cost of temporarily showing both the current document and an in-flight replacement job to the Admin.
