package com.mathshort.api.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.Instant;

@Getter @Setter
@NoArgsConstructor
@Entity
@Table(name = "users", uniqueConstraints = {
        @UniqueConstraint(name = "uk_users_username", columnNames = {"username"}),
        @UniqueConstraint(name = "uk_users_email", columnNames = {"email"}),
        @UniqueConstraint(name = "uk_users_provider_provider_id", columnNames = {"provider", "provider_id"})
})
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(length = 255, nullable = false)
    private String username;

    @Column(length = 20, nullable = false)
    private String provider;

    @Column(name = "provider_id", length = 200)
    private String providerId;

    @Column(length = 255)
    private String email;

    @Column(nullable = false)
    private Boolean verified = false;

    @Column(name = "verification_code", length = 6)
    private String verificationCode;

    @Column(name = "expires_at")
    private Instant expiresAt;

    @Column(name = "name", length = 100)
    private String name;

    @Column(name = "password_hash", length = 200, nullable = false)
    private String passwordHash;

    private Instant createdAt;

    @PrePersist
    public void prePersist() {
        createdAt = Instant.now();
        if (verified == null) verified = false;
    }
}
