package org.kiwiproject.dropwizard.jakarta.xml.ws.example.ws;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.ArgumentCaptor;
import jakarta.xml.ws.WebServiceContext;
import jakarta.xml.ws.handler.MessageContext;


/**
 * Professional JUnit 5 tests for JavaFirstServiceImpl
 * 
 * Tests focus on both happy path and edge cases.
 */
@ExtendWith(MockitoExtension.class)
class JavaFirstServiceImplTest {
    @Mock
    private WebServiceContext wsContext;

    private JavaFirstServiceImpl classUnderTest;

    @BeforeEach
    void setUp() {
        when(wsContext.getMessageContext()).thenReturn(mock(MessageContext.class));
        classUnderTest = new JavaFirstServiceImpl();
    }

    @Test
    void should_echo_valid_input() {
        // Given
        String input = "Hello, World!";
        
        // When
        var result = classUnderTest.echo(input);
        
        // Then
        assertThat(result).contains(input);
    }
    
    @Test
    void should_reject_invalid_input() {
        // Given
        String input = null;
        
        // When/Then
        assertThatThrownBy(() -> classUnderTest.echo(input))
            .isInstanceOf(Exception.class);
    }
    
    @Test
    void should_reject_empty_input() {
        // Given
        String input = "";
        
        // When/Then
        assertThatThrownBy(() -> classUnderTest.echo(input))
            .isInstanceOf(Exception.class);
    }

}
