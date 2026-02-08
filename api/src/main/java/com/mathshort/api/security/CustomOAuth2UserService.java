package com.mathshort.api.security;

import com.mathshort.api.domain.User;
import com.mathshort.api.repo.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.client.userinfo.DefaultOAuth2UserService;
import org.springframework.security.oauth2.client.userinfo.OAuth2UserRequest;
import org.springframework.security.oauth2.client.userinfo.OAuth2UserService;
import org.springframework.security.oauth2.core.OAuth2AuthenticationException;
import org.springframework.security.oauth2.core.user.DefaultOAuth2User;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class CustomOAuth2UserService implements OAuth2UserService<OAuth2UserRequest, OAuth2User> {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    @Override
    public OAuth2User loadUser(OAuth2UserRequest userRequest) throws OAuth2AuthenticationException {
        OAuth2User oauth2User = new DefaultOAuth2UserService().loadUser(userRequest);

        String registrationId = userRequest.getClientRegistration().getRegistrationId();
        String provider = registrationId.toUpperCase();

        if (!"GOOGLE".equals(provider)) {
            throw new OAuth2AuthenticationException("Unsupported provider: " + provider);
        }

        String providerId = valueAsString(oauth2User.getAttribute("sub"));
        if (providerId == null || providerId.isBlank()) {
            throw new OAuth2AuthenticationException("Google sub is missing");
        }

        String email = valueAsString(oauth2User.getAttribute("email"));
        String name = valueAsString(oauth2User.getAttribute("name"));

        User user = userRepository.findByProviderAndProviderId(provider, providerId)
                .orElseGet(() -> {
                    String username = buildUniqueUsername(email, provider, providerId);
                    User created = new User();
                    created.setUsername(username);
                    created.setProvider(provider);
                    created.setProviderId(providerId);
                    created.setEmail(email);
                    created.setName(name != null && !name.isBlank() ? name : username);
                    created.setPasswordHash(passwordEncoder.encode(UUID.randomUUID().toString()));
                    created.setVerified(true);
                    return userRepository.save(created);
                });

        if (user.getEmail() == null || !user.getEmail().equals(email)) {
            user.setEmail(email);
        }
        if (name != null && !name.isBlank() && !name.equals(user.getName())) {
            user.setName(name);
        }
        if (user.getUsername() == null || user.getUsername().isBlank()) {
            user.setUsername(buildUniqueUsername(email, provider, providerId));
        }
        user.setVerified(true);
        user.setVerificationCode(null);
        user.setExpiresAt(null);
        userRepository.save(user);

        Map<String, Object> attributes = new LinkedHashMap<>(oauth2User.getAttributes());
        attributes.put("username", user.getUsername());

        return new DefaultOAuth2User(
                Set.of(new SimpleGrantedAuthority("ROLE_USER")),
                attributes,
                "username"
        );
    }

    private static String valueAsString(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private static String buildUsername(String email, String provider, String providerId) {
        if (email != null && !email.isBlank()) {
            return email;
        }
        return provider.toLowerCase() + "_" + providerId;
    }

    private String buildUniqueUsername(String email, String provider, String providerId) {
        String base = buildUsername(email, provider, providerId);
        if (!userRepository.existsByUsername(base)) {
            return base;
        }

        int i = 1;
        while (userRepository.existsByUsername(base + "_" + i)) {
            i++;
        }
        return base + "_" + i;
    }
}
