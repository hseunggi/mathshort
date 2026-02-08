package com.mathshort.api.security;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    @Order(1)
    public SecurityFilterChain filterChain(HttpSecurity http, CustomOAuth2UserService customOAuth2UserService) throws Exception {
        http
            .csrf(csrf -> csrf.disable())
            .sessionManagement(sm -> sm.sessionCreationPolicy(SessionCreationPolicy.IF_REQUIRED))
            .authorizeHttpRequests(auth -> auth
                // ★ 에러/웰노운 허용 (403 루프 제거)
                .requestMatchers("/error", "/.well-known/**").permitAll()

                // oauth2 login endpoints
                .requestMatchers("/oauth2/**", "/login/oauth2/**").permitAll()

                // ★ auth는 GET/POST까지 확실히 허용
                .requestMatchers(HttpMethod.GET, "/auth/me").permitAll()
                .requestMatchers(HttpMethod.POST, "/auth/register", "/auth/login").permitAll()
                .requestMatchers("/auth/**").permitAll()

                // 정적/페이지
                .requestMatchers("/", "/index.html",
                        "/login", "/register", "/signup", "/signup/**",
                        "/login.html", "/register.html", "/signup.html", "/signup-email.html", "/signup-verify.html",
                        "/favicon.ico", "/assets/**",
                        "/*.css", "/*.js", "/*.png", "/*.ico").permitAll()

                // 보호 페이지 + API
                .requestMatchers("/app", "/mypage", "/app.html", "/mypage.html").authenticated()
                .requestMatchers("/v1/**").authenticated()

                // swagger
                .requestMatchers("/swagger-ui.html", "/swagger-ui/**", "/v3/api-docs/**").permitAll()

                // 나머지는 일단 열어둠(디버깅 끝나면 authenticated로 돌려도 됨)
                .anyRequest().permitAll()
            )
            .oauth2Login(oauth2 -> oauth2
                .loginPage("/login")
                .userInfoEndpoint(userInfo -> userInfo.userService(customOAuth2UserService))
                .defaultSuccessUrl("/app", true)
            )
            .httpBasic(b -> b.disable())
            .formLogin(f -> f.disable())
            .logout(l -> l.disable());

        return http.build();
    }

    @Bean
    public AuthenticationManager authenticationManager(AuthenticationConfiguration config) throws Exception {
        return config.getAuthenticationManager();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}
