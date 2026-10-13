package com.docintell.dto.ai;

import com.docintell.dto.ai.AiAnalyzeResponse.ExtractedFieldDto;
import com.docintell.dto.ai.AiAnalyzeResponse.OcrResultDto;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

public record AskQuestionRequestDto(
        String question,
        @JsonProperty("ocr_results")
        List<OcrResultDto> ocrResults,
        List<ExtractedFieldDto> fields,
        @JsonProperty("document_type")
        String documentType
) {}

