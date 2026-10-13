package com.docintell.dto.ai;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

@com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
public record AskQuestionResponseDto(
        String status,
        String question,
        String answer,
        String snippet,
        Double confidence,
        List<Integer> bbox,
        Integer page,
        @JsonProperty("matched_field")
        String matchedField,
        String message
) {}

