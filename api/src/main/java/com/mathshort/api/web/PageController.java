package com.mathshort.api.web;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class PageController {

    @GetMapping("/login")
    public String login() {
        return "forward:/login.html";
    }

    @GetMapping("/register")
    public String register() {
        return "forward:/register.html";
    }

    @GetMapping("/signup")
    public String signup() {
        return "forward:/signup.html";
    }

    @GetMapping("/signup/email")
    public String signupEmail() {
        return "forward:/signup-email.html";
    }

    @GetMapping("/signup/verify")
    public String signupVerify() {
        return "forward:/signup-verify.html";
    }

    @GetMapping("/terms")
    public String terms() {
        return "forward:/terms.html";
    }

    @GetMapping("/privacy")
    public String privacy() {
        return "forward:/privacy.html";
    }

    @GetMapping("/app")
    public String app() {
        return "forward:/app.html";
    }

    @GetMapping("/mypage")
    public String mypage() {
        return "forward:/mypage.html";
    }
}
