package com.mathshort.api.web;

import com.mathshort.api.domain.Job;
import com.mathshort.api.domain.JobStatus;
import com.mathshort.api.repo.JobRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;
import org.springframework.security.core.Authentication;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;

import java.net.MalformedURLException;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.UUID;

@RestController
@RequiredArgsConstructor
@RequestMapping("/v1/jobs")
public class JobController {

    private final JobRepository jobRepository;
    private final StringRedisTemplate redis;

    @Value("${storage.base:/data}")
    private String storageBase;

    private static final String QUEUE_KEY = "queue:jobs";
    private static final String VIDEO_QUEUE_KEY = "queue:video_jobs";

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Map<String, Object> createJob(@RequestPart("file") MultipartFile file, Authentication authentication) throws Exception {
        String original = file.getOriginalFilename();
        String ext = (original != null) ? StringUtils.getFilenameExtension(original) : null;

        if (ext == null || !ext.equalsIgnoreCase("png")) {
            throw new IllegalArgumentException("PNG 파일만 업로드 가능합니다.");
        }

        UUID jobId = UUID.randomUUID();

        Path uploadDir = Path.of(storageBase, "uploads");
        Files.createDirectories(uploadDir);

        Path inputPath = uploadDir.resolve(jobId + ".png");
        file.transferTo(inputPath);

        Job job = new Job();
        job.setId(jobId);
        job.setStatus(JobStatus.PENDING);
        job.setVideoStatus("NONE");
        job.setOwnerUsername(authentication.getName());
        job.setInputPngPath(inputPath.toString());
        jobRepository.save(job);

        redis.opsForList().leftPush(QUEUE_KEY, jobId.toString());

        return Map.of("jobId", jobId.toString(), "status", job.getStatus().name());
    }

    @PostMapping("/{jobId}/video")
    public Map<String, Object> createVideo(@PathVariable String jobId, Authentication authentication) {
        UUID id = UUID.fromString(jobId);
        Job job = jobRepository.findById(id).orElseThrow();
        if (job.getOwnerUsername() == null || !job.getOwnerUsername().equals(authentication.getName())) {
            throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.FORBIDDEN, "forbidden");
        }
        if (job.getDetailJson() == null || job.getDetailJson().isBlank()) {
            throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.BAD_REQUEST, "풀이가 먼저 생성되어야 합니다.");
        }

        String currentVideoStatus = job.getVideoStatus();
        if ("PENDING".equalsIgnoreCase(currentVideoStatus) || "RUNNING".equalsIgnoreCase(currentVideoStatus)) {
            return Map.of("jobId", job.getId().toString(), "videoStatus", currentVideoStatus);
        }

        job.setVideoStatus("PENDING");
        job.setVideoErrorMessage(null);
        jobRepository.save(job);

        redis.opsForList().leftPush(VIDEO_QUEUE_KEY, jobId);

        return Map.of("jobId", job.getId().toString(), "videoStatus", "PENDING");
    }

    @GetMapping("/{jobId}")
    public Map<String, Object> getJob(@PathVariable String jobId, Authentication authentication) {
        UUID id = UUID.fromString(jobId);
        Job job = jobRepository.findById(id).orElseThrow();
        if (job.getOwnerUsername() == null || !job.getOwnerUsername().equals(authentication.getName())) {
            throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.FORBIDDEN, "forbidden");
        }

        java.util.Map<String, Object> res = new java.util.LinkedHashMap<>();
        res.put("jobId", job.getId().toString());
        res.put("status", job.getStatus().name());
        res.put("videoStatus", job.getVideoStatus());
        res.put("inputPngPath", job.getInputPngPath());
        res.put("outputMp4Path", job.getOutputMp4Path());   // null 가능
        res.put("detailJson", job.getDetailJson());         // null 가능
        res.put("errorMessage", job.getErrorMessage());     // null 가능
        res.put("videoErrorMessage", job.getVideoErrorMessage());
        res.put("createdAt", job.getCreatedAt());
        res.put("updatedAt", job.getUpdatedAt());
        return res;
    }

    @GetMapping("/{jobId}/video")
    public ResponseEntity<Resource> getVideo(@PathVariable String jobId, Authentication authentication) throws Exception {
        UUID id = UUID.fromString(jobId);
        Job job = jobRepository.findById(id).orElseThrow();
        if (job.getOwnerUsername() == null || !job.getOwnerUsername().equals(authentication.getName())) {
            throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.FORBIDDEN, "forbidden");
        }

        String pathStr = job.getOutputMp4Path();
        if (pathStr == null || pathStr.isBlank()) {
            return ResponseEntity.notFound().build();
        }

        Path p = Path.of(pathStr);
        if (!Files.exists(p)) {
            return ResponseEntity.notFound().build();
        }

        Resource resource;
        try {
            resource = new UrlResource(p.toUri());
        } catch (MalformedURLException e) {
            return ResponseEntity.internalServerError().build();
        }

        return ResponseEntity.ok()
                .contentType(MediaType.valueOf("video/mp4"))
                .header(HttpHeaders.CONTENT_DISPOSITION, "inline; filename=\"" + id + ".mp4\"")
                .body(resource);
    }

}
