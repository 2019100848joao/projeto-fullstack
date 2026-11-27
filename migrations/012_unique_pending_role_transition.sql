CREATE UNIQUE INDEX ux_role_transition_requests_user_pending
    ON role_transition_requests (user_id)
    WHERE status = 'pending';
