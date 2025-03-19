package org.kiwiproject.dropwizard.jakarta.xml.ws.example.db;

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
import java.util.List;
import java.util.Optional;
import org.hibernate.Session;
import org.hibernate.SessionFactory;
import org.hibernate.Transaction;


/**
 * Professional JUnit 5 tests for PersonDAO
 * 
 * Tests focus on both happy path and edge cases.
 */
@ExtendWith(MockitoExtension.class)
class PersonDAOTest {
    @Mock
    private WebServiceContext wsContext;
    @Mock
    private SessionFactory sessionFactory;
    @Mock
    private Session session;
    @Mock
    private Transaction transaction;

    private PersonDAO classUnderTest;

    @BeforeEach
    void setUp() {
        when(sessionFactory.openSession()).thenReturn(session);
        when(session.getTransaction()).thenReturn(transaction);
        classUnderTest = new PersonDAO(sessionFactory);
    }

    @Test
    void should_find_all_records() {
        // Given
        var mockQuery = mock(org.hibernate.query.Query.class);
        var expectedResults = List.of(mock(Object.class), mock(Object.class));
        
        when(session.createNamedQuery(anyString())).thenReturn(mockQuery);
        when(mockQuery.list()).thenReturn(expectedResults);
        
        // When
        var result = classUnderTest.findAll();
        
        // Then
        assertThat(result).hasSize(2);
        assertThat(result).isSameAs(expectedResults);
        verify(session).createNamedQuery(anyString());
        verify(mockQuery).list();
    }
    
    @Test
    void should_return_empty_list_when_no_records_exist() {
        // Given
        var mockQuery = mock(org.hibernate.query.Query.class);
        var emptyList = List.of();
        
        when(session.createNamedQuery(anyString())).thenReturn(mockQuery);
        when(mockQuery.list()).thenReturn(emptyList);
        
        // When
        var result = classUnderTest.findAll();
        
        // Then
        assertThat(result).isEmpty();
        verify(session).createNamedQuery(anyString());
        verify(mockQuery).list();
    }

    @Test
    void should_find_by_id_when_record_exists() {
        // Given
        Long id = 1L;
        var expectedEntity = mock(Object.class);
        when(session.get(any(), eq(id))).thenReturn(expectedEntity);
        
        // When
        var result = classUnderTest.findById(id);
        
        // Then
        assertThat(result).isPresent();
        assertThat(result.get()).isSameAs(expectedEntity);
        verify(session).get(any(), eq(id));
    }
    
    @Test
    void should_return_empty_optional_when_record_not_found() {
        // Given
        Long id = 999L;
        when(session.get(any(), eq(id))).thenReturn(null);
        
        // When
        var result = classUnderTest.findById(id);
        
        // Then
        assertThat(result).isEmpty();
        verify(session).get(any(), eq(id));
    }

    @Test
    void should_create_entity_successfully() {
        // Given
        var entity = mock(Object.class);
        when(session.persist(any())).thenReturn(entity);
        
        // When
        var result = classUnderTest.create(entity);
        
        // Then
        assertThat(result).isSameAs(entity);
        verify(session).persist(entity);
        verify(transaction, never()).rollback();
    }
    
    @Test
    void should_handle_exception_during_create() {
        // Given
        var entity = mock(Object.class);
        when(session.persist(any())).thenThrow(new RuntimeException("Database error"));
        
        // When/Then
        assertThatThrownBy(() -> classUnderTest.create(entity))
            .isInstanceOf(RuntimeException.class)
            .hasMessageContaining("Database error");
            
        verify(session).persist(entity);
    }

}
