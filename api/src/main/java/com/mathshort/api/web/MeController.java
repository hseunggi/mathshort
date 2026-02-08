package com.mathshort.api.web;

import com.mathshort.api.repo.JobRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

import org.springframework.security.core.Authentication;

@RestController
@RequiredArgsConstructor
@RequestMapping("/v1/me")
public class MeController {

    private final JobRepository jobRepository;

    @GetMapping("/jobs")
    public List<Map<String, Object>> myJobs(Authentication authentication) {
        String username = authentication.getName();
        return jobRepository.findByOwnerUsernameOrderByCreatedAtDesc(username).stream()
                .map(j -> {
                    Map<String, Object> row = new java.util.LinkedHashMap<>();
                    row.put("jobId", j.getId().toString());
                    row.put("status", j.getStatus().name());
                    row.put("videoStatus", j.getVideoStatus());
                    row.put("createdAt", j.getCreatedAt());
                    row.put("updatedAt", j.getUpdatedAt());
                    row.put("hasVideo", j.getOutputMp4Path() != null && !j.getOutputMp4Path().isBlank());
                    row.put("detailJson", j.getDetailJson());
                    return row;
                })
                .toList();
    }
}
