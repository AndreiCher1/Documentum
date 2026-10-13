package com.docintell.dto;

import jakarta.validation.constraints.NotBlank;

public record DocumentAskRequest(
        @NotBlank(message = "Вопрос не может быть пустым")
        String question
) {}
