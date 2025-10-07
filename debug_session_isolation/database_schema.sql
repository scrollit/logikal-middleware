--
-- PostgreSQL database dump
--

\restrict snuKzPFv90kD5IgtNCQ0dfEadHp7ALaP39d6l3Vt4kRwotTpXzilog7ONXUl3kW

-- Dumped from database version 15.14 (Debian 15.14-1.pgdg13+1)
-- Dumped by pg_dump version 15.14 (Debian 15.14-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: projects; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.projects (
    id integer NOT NULL,
    logikal_id character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    directory_id integer,
    status character varying(50),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    last_sync_date timestamp with time zone,
    last_update_date timestamp with time zone
);


ALTER TABLE public.projects OWNER TO admin;

--
-- Name: COLUMN projects.last_sync_date; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.projects.last_sync_date IS 'Last time data was synced from Logikal';


--
-- Name: COLUMN projects.last_update_date; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.projects.last_update_date IS 'Last time data was modified in Logikal';


--
-- Name: projects_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.projects_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.projects_id_seq OWNER TO admin;

--
-- Name: projects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.projects_id_seq OWNED BY public.projects.id;


--
-- Name: projects id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.projects ALTER COLUMN id SET DEFAULT nextval('public.projects_id_seq'::regclass);


--
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- Name: ix_projects_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ix_projects_id ON public.projects USING btree (id);


--
-- Name: ix_projects_logikal_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX ix_projects_logikal_id ON public.projects USING btree (logikal_id);


--
-- Name: projects projects_directory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_directory_id_fkey FOREIGN KEY (directory_id) REFERENCES public.directories(id);


--
-- PostgreSQL database dump complete
--

\unrestrict snuKzPFv90kD5IgtNCQ0dfEadHp7ALaP39d6l3Vt4kRwotTpXzilog7ONXUl3kW

