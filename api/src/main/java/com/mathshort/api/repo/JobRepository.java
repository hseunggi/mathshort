package com.mathshort.api.repo;

import com.mathshort.api.domain.Job;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface JobRepository extends JpaRepository<Job, UUID> {
    List<Job> findByOwnerUsernameOrderByCreatedAtDesc(String ownerUsername);
}
