package com.docintell.dto.ai;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

@com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
public record AiAnalyzeResponse(
        String status,
        @JsonProperty("processing_time_ms")
        Double processingTimeMs,
        @JsonProperty("total_pages")
        Integer totalPages,
        QualityMetricsDto quality,
        @JsonProperty("document_type")
        DocumentTypeDto documentType,
        @JsonProperty("ocr_results")
        List<OcrResultDto> ocrResults,
        List<ExtractedFieldDto> fields,
        ValidationSummaryDto validation,
        @JsonProperty("overall_confidence")
        Double overallConfidence,
        String message
) {
    @com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
    public record ValidationSummaryDto(
            @JsonProperty("overall_status")
            String overallStatus,
            @JsonProperty("total_rules")
            Integer totalRules,
            @JsonProperty("passed_rules")
            Integer passedRules,
            @JsonProperty("warning_rules")
            Integer warningRules,
            @JsonProperty("failed_rules")
            Integer failedRules,
            List<RuleResultDto> rules
    ) {}

    @com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
    public record RuleResultDto(
            @JsonProperty("rule_id")
            String ruleId,
            @JsonProperty("rule_name")
            String ruleName,
            String status,
            String message,
            @JsonProperty("field_name")
            String fieldName
    ) {}
    public record QualityMetricsDto(
            @JsonProperty("blur_score")
            Double blurScore,
            @JsonProperty("is_blurry")
            Boolean isBlurry,
            Double brightness,
            Double contrast,
            Integer width,
            Integer height,
            @JsonProperty("skew_angle")
            Double skewAngle
    ) {}

    @com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
    public record DocumentTypeDto(
            String type,
            Double confidence,
            @JsonProperty("display_name")
            String displayName,
            String explanation,
            @JsonProperty("matched_keywords")
            List<String> matchedKeywords
    ) {
        public DocumentTypeDto(String type, Double confidence) {
            this(type, confidence, null, null, null);
        }
    }

    public record OcrResultDto(
            String text,
            Double confidence,
            List<Integer> bbox,
            Integer page
    ) {}

    public record ExtractedFieldDto(
            String name,
            @JsonProperty("display_name")
            String displayName,
            String value,
            @JsonProperty("field_type")
            String fieldType,
            Double confidence,
            List<Integer> bbox,
            Integer page
    ) {}
}

