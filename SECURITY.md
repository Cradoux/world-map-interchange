# Security

WMI packages are meant to be exchanged between tools and users, so readers must treat them as untrusted. The
specification's safe-reading rules (section 3.5) and the reference validator guard against path traversal, symlinks,
duplicate entries, archive bombs and oversized images.

If you find a way to make the reference tools read outside a package, follow a link, exhaust memory despite the limits,
or crash on crafted input, please report it **privately**. Use GitHub's "Report a vulnerability" button on the repository's
Security tab if it is enabled, or contact the repository owner through their GitHub profile. Please don't open a public
issue with a working exploit.

Weaknesses in the specification itself (for example a rule that encourages unsafe extraction) can be discussed in public
issues.
