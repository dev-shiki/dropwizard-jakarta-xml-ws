package org.kiwiproject.dropwizard.jakarta.xml.ws.example.resources;

import org.apache.cxf.helpers.IOUtils;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.Mockito;
import org.mockito.junit.jupiter.MockitoExtension;
import ws.example.ws.xml.jakarta.dropwizard.kiwiproject.org.mtomservice.Hello;
import ws.example.ws.xml.jakarta.dropwizard.kiwiproject.org.mtomservice.HelloResponse;
import ws.example.ws.xml.jakarta.dropwizard.kiwiproject.org.mtomservice.MtomService;
import ws.example.ws.xml.jakarta.dropwizard.kiwiproject.org.mtomservice.ObjectFactory;

import jakarta.activation.DataHandler;
import jakarta.mail.util.ByteArrayDataSource;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
public class AccessMtomServiceResourceTest {

    @Mock
    private MtomService mtomServiceClient;

    private AccessMtomServiceResource resource;

    @BeforeEach
    public void setUp() {
        resource = new AccessMtomServiceResource(mtomServiceClient);
    }

    @Test
    public void shouldReturnHelloResponse_whenGetFooIsCalled() throws IOException {
        // Given
        var objectFactory = new ObjectFactory();
        var hello = objectFactory.createHello();
        hello.setTitle("Hello");
        hello.setBinary(new DataHandler(new ByteArrayDataSource("test".getBytes(), "text/plain")));

        var helloResponse = objectFactory.createHelloResponse();
        helloResponse.setTitle("Hello Response");
        helloResponse.setBinary(new DataHandler(new ByteArrayDataSource("response".getBytes(), "text/plain")));

        when(mtomServiceClient.hello(any(Hello.class))).thenReturn(helloResponse);

        // When
        String result = resource.getFoo();

        // Then
        assertThat(result).isEqualTo("Hello response: Hello Response, response at " + LocalDateTime.now().toLocalDate());
    }

    @Test
    public void shouldThrowUncheckedIOException_whenIOExceptionOccurs() throws IOException {
        // Given
        var objectFactory = new ObjectFactory();
        var hello = objectFactory.createHello();
        hello.setTitle("Hello");
        hello.setBinary(new DataHandler(new ByteArrayDataSource("test".getBytes(), "text/plain")));

        var helloResponse = objectFactory.createHelloResponse();
        helloResponse.setTitle("Hello Response");
        helloResponse.setBinary(new DataHandler(new ByteArrayDataSource("response".getBytes(), "text/plain")));

        when(mtomServiceClient.hello(any(Hello.class))).thenReturn(helloResponse);

        // Mocking the IOUtils.readStringFromStream to throw IOException
        Mockito.when(IOUtils.readStringFromStream(any(ByteArrayInputStream.class))).thenThrow(new IOException("Mocked IOException"));

        // When/Then
        assertThatThrownBy(() -> resource.getFoo())
                .isInstanceOf(UncheckedIOException.class)
                .hasCauseInstanceOf(IOException.class)
                .hasMessageContaining("Mocked IOException");
    }

    @Test
    public void shouldHandleNullBinaryData_whenGetFooIsCalled() throws IOException {
        // Given
        var objectFactory = new ObjectFactory();
        var hello = objectFactory.createHello();
        hello.setTitle("Hello");
        hello.setBinary(null);

        var helloResponse = objectFactory.createHelloResponse();
        helloResponse.setTitle("Hello Response");
        helloResponse.setBinary(null);

        when(mtomServiceClient.hello(any(Hello.class))).thenReturn(helloResponse);

        // When
        String result = resource.getFoo();

        // Then
        assertThat(result).isEqualTo("Hello response: Hello Response,  at " + LocalDateTime.now().toLocalDate());
    }

    @Test
    public void shouldHandleEmptyBinaryData_whenGetFooIsCalled() throws IOException {
        // Given
        var objectFactory = new ObjectFactory();
        var hello = objectFactory.createHello();
        hello.setTitle("Hello");
        hello.setBinary(new DataHandler(new ByteArrayDataSource("".getBytes(), "text/plain")));

        var helloResponse = objectFactory.createHelloResponse();
        helloResponse.setTitle("Hello Response");
        helloResponse.setBinary(new DataHandler(new ByteArrayDataSource("".getBytes(), "text/plain")));

        when(mtomServiceClient.hello(any(Hello.class))).thenReturn(helloResponse);

        // When
        String result = resource.getFoo();

        // Then
        assertThat(result).isEqualTo("Hello response: Hello Response,  at " + LocalDateTime.now().toLocalDate());
    }
}