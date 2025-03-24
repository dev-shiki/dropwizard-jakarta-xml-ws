package org.kiwiproject.dropwizard.jakarta.xml.ws.example.ws;

import jakarta.xml.ws.AsyncHandler;
import jakarta.xml.ws.Response;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.Mockito;
import org.mockito.junit.jupiter.MockitoExtension;
import ws.example.ws.xml.jakarta.dropwizard.kiwiproject.org.wsdlfirstservice.Echo;
import ws.example.ws.xml.jakarta.dropwizard.kiwiproject.org.wsdlfirstservice.EchoResponse;
import ws.example.ws.xml.jakarta.dropwizard.kiwiproject.org.wsdlfirstservice.NonBlockingEcho;
import ws.example.ws.xml.jakarta.dropwizard.kiwiproject.org.wsdlfirstservice.WsdlFirstService;

import java.util.concurrent.ExecutionException;
import java.util.concurrent.Future;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class WsdlFirstServiceImplTest {

    private WsdlFirstServiceImpl service;

    @Mock
    private AsyncHandler<EchoResponse> asyncHandler;

    @BeforeEach
    public void setUp() {
        service = new WsdlFirstServiceImpl();
    }

    @Test
    public void shouldEchoValue_whenEchoCalled() {
        // Given
        var echoRequest = new Echo();
        echoRequest.setValue("testValue");

        // When
        var response = service.echo(echoRequest);

        // Then
        assertThat(response.getValue()).isEqualTo("testValue");
    }

    @Test
    public void shouldReturnBlockingResponse_whenNonBlockingEchoCalled() {
        // Given
        var nonBlockingEchoRequest = new NonBlockingEcho();
        nonBlockingEchoRequest.setValue("testValue");

        // When
        var response = service.nonBlockingEcho(nonBlockingEchoRequest);

        // Then
        assertThat(response.getValue()).isEqualTo("Blocking: testValue");
    }

    @Test
    public void shouldReturnNonBlockingResponse_whenNonBlockingEchoAsyncCalled() throws ExecutionException, InterruptedException {
        // Given
        var nonBlockingEchoRequest = new NonBlockingEcho();
        nonBlockingEchoRequest.setValue("testValue");

        // When
        Future<EchoResponse> futureResponse = service.nonBlockingEchoAsync(nonBlockingEchoRequest, asyncHandler);
        EchoResponse response = futureResponse.get();

        // Then
        assertThat(response.getValue()).isEqualTo("Non-blocking: testValue");
        verify(asyncHandler, times(1)).handleResponse(any(Response.class));
    }

    @Test
    public void shouldHandleInterruptedException_whenNonBlockingEchoAsyncThrowsInterruptedException() throws ExecutionException, InterruptedException {
        // Given
        var nonBlockingEchoRequest = new NonBlockingEcho();
        nonBlockingEchoRequest.setValue("testValue");

        // Mocking the behavior to throw InterruptedException
        doAnswer(invocation -> {
            var asyncResponse = (ServerAsyncResponse<EchoResponse>) invocation.getArguments()[0];
            asyncResponse.exception(new InterruptedException("Mocked interruption"));
            return null;
        }).when(asyncHandler).handleResponse(any(Response.class));

        // When
        Future<EchoResponse> futureResponse = service.nonBlockingEchoAsync(nonBlockingEchoRequest, asyncHandler);
        try {
            futureResponse.get();
        } catch (ExecutionException e) {
            // Then
            assertThat(e.getCause()).isInstanceOf(InterruptedException.class);
        }

        verify(asyncHandler, times(1)).handleResponse(any(Response.class));
    }

    @Test
    public void shouldHandleNullValue_whenEchoCalledWithNull() {
        // Given
        var echoRequest = new Echo();
        echoRequest.setValue(null);

        // When
        var response = service.echo(echoRequest);

        // Then
        assertThat(response.getValue()).isNull();
    }

    @Test
    public void shouldHandleNullValue_whenNonBlockingEchoCalledWithNull() {
        // Given
        var nonBlockingEchoRequest = new NonBlockingEcho();
        nonBlockingEchoRequest.setValue(null);

        // When
        var response = service.nonBlockingEcho(nonBlockingEchoRequest);

        // Then
        assertThat(response.getValue()).isEqualTo("Blocking: null");
    }

    @Test
    public void shouldHandleNullValue_whenNonBlockingEchoAsyncCalledWithNull() throws ExecutionException, InterruptedException {
        // Given
        var nonBlockingEchoRequest = new NonBlockingEcho();
        nonBlockingEchoRequest.setValue(null);

        // When
        Future<EchoResponse> futureResponse = service.nonBlockingEchoAsync(nonBlockingEchoRequest, asyncHandler);
        EchoResponse response = futureResponse.get();

        // Then
        assertThat(response.getValue()).isEqualTo("Non-blocking: null");
        verify(asyncHandler, times(1)).handleResponse(any(Response.class));
    }
}