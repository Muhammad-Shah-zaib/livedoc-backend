def get_key_for_document(share_token):
    """
    Generate a Redis key for a document based on its ID.
    """
    return f"doc:{share_token}:users"