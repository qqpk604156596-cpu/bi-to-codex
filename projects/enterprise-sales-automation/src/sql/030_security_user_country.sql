-- Simulated RLS mapping for this public-data practice case only.
-- Do not substitute real user identities or run this file against a client database without approval.

CREATE TABLE IF NOT EXISTS `security_user_country` (
    `UserPrincipalName` VARCHAR(320) NOT NULL,
    `Country` VARCHAR(100) NOT NULL,
    `IsActive` BOOLEAN NOT NULL,
    PRIMARY KEY (`UserPrincipalName`, `Country`)
);

DELETE FROM `security_user_country`
WHERE `UserPrincipalName` IN (
    'manager.uk@example.invalid',
    'manager.fr@example.invalid'
);

INSERT INTO `security_user_country` (`UserPrincipalName`, `Country`, `IsActive`) VALUES
    ('manager.uk@example.invalid', 'United Kingdom', TRUE),
    ('manager.fr@example.invalid', 'France', TRUE);

-- unmapped.manager@example.invalid deliberately has no row and must see no protected facts.
