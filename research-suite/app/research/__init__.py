"""
Question framing and search-strategy construction.

The modules here sit *before* retrieval: they turn a clinical question into the
search strings that `sources/` executes, and they record the strategy so it can be
reported. A systematic review is judged on its search strategy as much as its
findings, and a strategy that was never written down cannot be appraised or
reproduced.
"""
