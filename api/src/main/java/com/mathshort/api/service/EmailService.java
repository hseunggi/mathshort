package com.mathshort.api.service;

import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class EmailService {

    private static final Logger log = LoggerFactory.getLogger(EmailService.class);
    private static final String SUBJECT = "Mathshort 이메일 인증 코드";

    private final JavaMailSender mailSender;
    @Value("${spring.mail.username:}")
    private String fromAddress;

    public void sendVerificationCode(String to, String code) {
        if (fromAddress == null || fromAddress.isBlank()) {
            log.error("Email send failed: MAIL_USERNAME is empty. to={}, subject={}", to, SUBJECT);
            throw new EmailSendException("인증 메일 발송 실패");
        }

        SimpleMailMessage message = new SimpleMailMessage();
        message.setFrom(fromAddress);
        message.setTo(to);
        message.setSubject(SUBJECT);
        message.setText("아래 인증 코드를 입력해 주세요.\n\n인증 코드: " + code + "\n\n유효 시간: 10분");

        log.info("Email send start: to={}, subject={}", to, SUBJECT);

        try {
            mailSender.send(message);
            log.info("Email send success: to={}, subject={}, messageId={}", to, SUBJECT, "N/A");
        } catch (Exception e) {
            log.error("Email send fail: to={}, subject={}, error={}", to, SUBJECT, e.getMessage(), e);
            throw new EmailSendException("인증 메일 발송 실패", e);
        }
    }
}
