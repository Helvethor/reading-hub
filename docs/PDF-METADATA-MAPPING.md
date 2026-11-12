# PDF metadata mapping

Generated PDFs use WeasyPrint's document metadata for the standard PDF
information dictionary and standard XMP fields. The Reading Hub extension uses
the stable namespace `urn:reading-hub:pdf:1.0`. It is a bounded projection, not
a serialization of the rendition's arbitrary metadata or evidence JSON.

| PDF/XMP property | Source |
|---|---|
| PDF `/Title`, XMP `dc:title` | Exact rendition title |
| PDF `/Author`, XMP `dc:creator` | Explicit work author(s), including contributors whose role is `author`; no fallback website name |
| PDF `/Keywords`, XMP `dc:subject` | Explicit subject/topic strings |
| XMP `dc:contributor` | Named editors, translators, and explicitly unconfirmed contributors |
| XMP `dc:language`, PDF catalog `/Lang` | Explicit language tag |
| PDF `/CreationDate`, XMP `xmp:CreateDate` | Actual UTC PDF render time |
| `rh:editor`, `rh:translator`, `rh:unknown` | Contributor names grouped by recorded role; excluded contributors are omitted |
| `rh:dateFact` | Exact written, delivered, publication, online-edition, or role-unconfirmed date values and optional end values |
| `rh:sourceURL`, `rh:renditionIdentity`, `rh:outputDigest` | Public source URL and exact source-generated rendition identity/digest |
| `rh:sourceCaptureDate` | Source snapshot fetch time, distinct from work dates |
| `rh:editionOrigin`, `rh:editionRevision`, `rh:sourceRenditionIdentity` | Published/source-generated origin and exact saved revision/source-edition identity |
| `rh:reviewScope`, `rh:verifiedSection`, `rh:reviewEditorialChanges` | Recorded review scope only; publication does not promote or recompute review |
| `rh:publicationRuleVersion`, `rh:appVersion`, `rh:adapterVersion`, `rh:formatVersion` | Bounded generation provenance |
| `rh:draftContentState`, `rh:historicalReview` | Request-time draft state and clearly historical base-review context when present |
| `rh:workType`, `rh:originalTitle`, `rh:publisher`, `rh:series`, `rh:sourceEdition`, `rh:rights` | Explicit bibliographic facts when present |

Empty and unknown values are omitted unless the source explicitly records an
unknown contributor/date role. Original work dates remain `rh:dateFact`; they
are never mapped to PDF `CreationDate`. Source capture time remains separate
from the actual PDF creation time. No source or modification timestamp is
invented.

The mapping excludes reviewer/account identifiers, private annotations,
credentials, signing or recovery tokens, local paths, private workspace URLs,
and arbitrary metadata/evidence. Bibliographic names are included only as
work facts with their recorded roles. Standard fields and XMP describe the
same rendition title, explicit authors, subjects, and language. This metadata
does not imply PDF/A conformance, signatures, or survival through third-party
editing or re-export.
