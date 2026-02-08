package com.mathshort.api.web;

import com.mathshort.api.domain.User;
import com.mathshort.api.repo.UserRepository;
import com.mathshort.api.service.EmailSendException;
import com.mathshort.api.service.EmailService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;

@RestController
@RequiredArgsConstructor
@RequestMapping("/auth")
public class AuthController {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final AuthenticationManager authenticationManager;
    private final EmailService emailService;

    @PostMapping("/register")
    public Map<String, Object> register(@RequestBody RegisterReq req) {
        String username = safe(req.username);
        String password = safe(req.password);

        if (username.length() < 3 || username.length() > 64) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "username은 3~64자여야 합니다.");
        }
        if (password.length() < 6 || password.length() > 200) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "password는 6~200자여야 합니다.");
        }
        if (userRepository.existsByUsername(username)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 존재하는 username 입니다.");
        }

        User u = new User();
        u.setUsername(username);
        u.setProvider("LOCAL");
        u.setProviderId(null);
        u.setEmail(null);
        u.setName(username);
        u.setPasswordHash(passwordEncoder.encode(password));
        u.setVerified(true);
        userRepository.save(u);

        // 가입 후 자동 로그인
        Authentication auth = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(username, password)
        );
        SecurityContextHolder.getContext().setAuthentication(auth);

        return Map.of("username", username);
    }

    @PostMapping("/login")
    public Map<String, Object> login(@RequestBody LoginReq req, HttpServletRequest request) {
        String username = safe(req.username);
        String password = safe(req.password);

        Authentication auth = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(username, password)
        );
        SecurityContextHolder.getContext().setAuthentication(auth);

        // 세션 생성(쿠키)
        HttpSession session = request.getSession(true);
        session.setAttribute("SPRING_SECURITY_CONTEXT", SecurityContextHolder.getContext());

        return Map.of("username", username);
    }

    @PostMapping("/logout")
    public Map<String, Object> logout(HttpServletRequest request) {
        SecurityContextHolder.clearContext();
        HttpSession session = request.getSession(false);
        if (session != null) session.invalidate();
        return Map.of("ok", true);
    }

    @PostMapping("/email/signup-start")
    @Transactional
    public Map<String, Object> emailSignupStart(@RequestBody EmailSignupReq req) {
        String email = normalizeEmail(req.email);
        String password = safe(req.password);

        if (!isValidEmail(email)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "올바른 이메일 형식이 아닙니다.");
        }
        if (password.length() < 6 || password.length() > 200) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "password는 6~200자여야 합니다.");
        }

        User user = userRepository.findByEmail(email).orElse(null);
        if (user != null && !"LOCAL".equals(user.getProvider())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 소셜 로그인으로 가입된 이메일입니다.");
        }

        if (user == null) {
            user = new User();
            user.setUsername(buildUniqueLocalUsername(email));
            user.setProvider("LOCAL");
            user.setProviderId(null);
            user.setEmail(email);
            user.setName(email);
        } else if (Boolean.TRUE.equals(user.getVerified())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 가입된 이메일입니다. 로그인 해주세요.");
        }

        String code = random6Digits();
        user.setPasswordHash(passwordEncoder.encode(password));
        user.setVerified(false);
        user.setVerificationCode(code);
        user.setExpiresAt(Instant.now().plusSeconds(10 * 60));
        userRepository.save(user);

        emailService.sendVerificationCode(email, code);

        String encodedEmail = URLEncoder.encode(email, StandardCharsets.UTF_8);
        return Map.of(
                "ok", true,
                "next", "/signup/verify?email=" + encodedEmail
        );
    }

    @PostMapping("/email/resend")
    @Transactional
    public Map<String, Object> emailResend(@RequestBody EmailResendReq req) {
        String email = normalizeEmail(req.email);

        User user = userRepository.findByEmailAndProvider(email, "LOCAL")
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "가입 정보를 찾을 수 없습니다."));

        if (Boolean.TRUE.equals(user.getVerified())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "이미 인증된 계정입니다.");
        }

        String code = random6Digits();
        user.setVerificationCode(code);
        user.setExpiresAt(Instant.now().plusSeconds(10 * 60));
        userRepository.save(user);

        emailService.sendVerificationCode(email, code);
        return Map.of("ok", true);
    }

    @PostMapping("/email/verify")
    public Map<String, Object> emailVerify(@RequestBody EmailVerifyReq req) {
        String email = normalizeEmail(req.email);
        String code = safe(req.code);

        User user = userRepository.findByEmailAndProvider(email, "LOCAL")
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "가입 정보를 찾을 수 없습니다."));

        if (Boolean.TRUE.equals(user.getVerified())) {
            return Map.of("ok", true);
        }
        if (user.getVerificationCode() == null || !user.getVerificationCode().equals(code)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "인증 코드가 올바르지 않습니다.");
        }
        if (user.getExpiresAt() == null || user.getExpiresAt().isBefore(Instant.now())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "인증 코드가 만료되었습니다.");
        }

        user.setVerified(true);
        user.setVerificationCode(null);
        user.setExpiresAt(null);
        userRepository.save(user);

        return Map.of("ok", true);
    }

    @PostMapping("/email/login")
    public Map<String, Object> emailLogin(@RequestBody EmailLoginReq req, HttpServletRequest request) {
        String email = normalizeEmail(req.email);
        String password = safe(req.password);

        User user = userRepository.findByEmailAndProvider(email, "LOCAL")
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다."));

        if (!Boolean.TRUE.equals(user.getVerified())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "이메일 인증이 필요합니다.");
        }

        Authentication auth = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(user.getUsername(), password)
        );
        SecurityContextHolder.getContext().setAuthentication(auth);

        HttpSession session = request.getSession(true);
        session.setAttribute("SPRING_SECURITY_CONTEXT", SecurityContextHolder.getContext());

        return Map.of("username", user.getUsername(), "email", user.getEmail());
    }

    @GetMapping("/me")
    public Map<String, Object> me(Authentication authentication) {
        if (authentication == null || !authentication.isAuthenticated()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "not logged in");
        }
        return Map.of("username", authentication.getName());
    }

    @ExceptionHandler(EmailSendException.class)
    public ResponseEntity<Map<String, Object>> handleEmailSendFail(EmailSendException e) {
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                .body(Map.of("message", "인증 메일 발송 실패"));
    }

    private static String safe(String s) {
        return (s == null) ? "" : s.trim();
    }

    private static String normalizeEmail(String s) {
        return safe(s).toLowerCase();
    }

    private static boolean isValidEmail(String email) {
        return email.length() >= 5 && email.length() <= 255 && email.contains("@") && email.contains(".");
    }

    private static String random6Digits() {
        int n = ThreadLocalRandom.current().nextInt(100000, 1_000_000);
        return Integer.toString(n);
    }

    private String buildUniqueLocalUsername(String email) {
        if (!userRepository.existsByUsername(email)) {
            return email;
        }
        int i = 1;
        while (userRepository.existsByUsername(email + "_" + i)) {
            i++;
        }
        return email + "_" + i;
    }

    @Data
    public static class RegisterReq {
        @NotBlank public String username;
        @NotBlank public String password;
    }

    @Data
    public static class LoginReq {
        @NotBlank public String username;
        @NotBlank public String password;
    }

    @Data
    public static class EmailSignupReq {
        @NotBlank public String email;
        @NotBlank public String password;
    }

    @Data
    public static class EmailVerifyReq {
        @NotBlank public String email;
        @NotBlank public String code;
    }

    @Data
    public static class EmailLoginReq {
        @NotBlank public String email;
        @NotBlank public String password;
    }

    @Data
    public static class EmailResendReq {
        @NotBlank public String email;
    }
}
