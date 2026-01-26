"""Agent Forge page - promote entities to active agents with personas.



Allows users to:

- View promotable entities from intel.duckdb

- Create system prompts and persona definitions

- Define agent goals, capabilities, and initial states

- Toggle entity activation status

"""



import streamlit as st

import json

import pandas as pd

from typing import Dict, Any, List

from forge.sandbox.session import Session



class AgentForgePage:

    """Agent Forge page implementation."""

    

    def __init__(self, session: Session):

        self.session = session

    

    def render(self):

        """Render the Agent Forge page."""

        st.header("👤 Agent Forge")

        st.markdown("### Transform Entities into Active Simulation Agents")

        st.markdown("Promote extracted entities to active agents by defining their personas, goals, and capabilities for your simulation world.")

        

        if not self.session.db:

            st.error("❌ No database connection. Please select a project first.")

            return

        

        try:

            # Load data

            entities_df = self._load_promotable_entities()

            active_agents_df = self._load_active_agents()

            

            if entities_df.empty:

                self._render_empty_state()

                return

            

            # Main layout

            col1, col2 = st.columns([1, 2])

            

            with col1:

                self._render_entity_selector(entities_df, active_agents_df)

            

            with col2:

                self._render_agent_editor()

                

        except Exception as e:

            st.error(f"❌ Error loading agent forge: {e}")

            st.code(str(e))

    

    def _load_promotable_entities(self) -> pd.DataFrame:

        """Load entities that can be promoted to agents."""

        if not self.session.db or not self.session.db.world_conn:

            return pd.DataFrame()

        return self.session.db.world_conn.execute("""

            SELECT 

                r.id, r.type, r.label, r.attributes_json,

                CASE WHEN w.agent_id IS NOT NULL THEN TRUE ELSE FALSE END as is_active,

                w.persona_prompt, w.goals, w.capabilities, w.state

            FROM raw_db.entities r

            LEFT JOIN active_agents w ON r.id = w.agent_id

            WHERE r.type IN ('PERSON', 'ORGANIZATION', 'CHARACTER', 'ENTITY')

            ORDER BY r.type, r.label

        """).df()

    

    def _load_active_agents(self) -> pd.DataFrame:

        """Load currently active agents."""

        if not self.session.db or not self.session.db.world_conn:

            return pd.DataFrame()

        return self.session.db.world_conn.execute("""

            SELECT 

                aa.agent_id, aa.persona_prompt, aa.goals, aa.capabilities, aa.state,

                aa.created_at, aa.updated_at,

                e.label, e.type, e.attributes_json

            FROM active_agents aa

            JOIN raw_db.entities e ON aa.agent_id = e.id

            ORDER BY aa.updated_at DESC

        """).df()

    

    def _render_empty_state(self):

        """Render empty state when no entities are available."""

        st.info("🤖 **No promotable entities found**")

        st.markdown("""

        To create agents, you need entities that can be promoted:

        

        1. **Extract Entities:** Use the Flet Extractor to process documents

        2. **Entity Types:** Look for PERSON, ORGANIZATION, or CHARACTER entities

        3. **Return Here:** Suitable entities will appear for agent promotion

        

        **Ideal agent candidates:**

        - 👤 **People:** Historical figures, experts, decision-makers  

        - 🏢 **Organizations:** Companies, governments, factions

        - 🎭 **Characters:** Fictional personas, archetypes

        """)

    

    def _render_entity_selector(self, entities_df: pd.DataFrame, active_agents_df: pd.DataFrame):

        """Render entity selection sidebar."""

        st.subheader("📋 Available Entities")

        

        # Filter controls

        entity_types = sorted(entities_df['type'].unique())

        selected_types = st.multiselect(

            "Filter by Type",

            entity_types,

            default=entity_types

        )

        

        show_active_only = st.checkbox("Show active agents only", value=False)

        

        # Apply filters

        filtered_df = entities_df[entities_df['type'].isin(selected_types)]

        if show_active_only:

            filtered_df = filtered_df[filtered_df['is_active'] == True]

        

        # Summary stats

        active_count = len(filtered_df[filtered_df['is_active'] == True])

        total_count = len(filtered_df)

        st.markdown(f"**{active_count}/{total_count} active agents**")

        

        # Entity list

        for _, entity in filtered_df.iterrows():

            self._render_entity_card(entity)

    

    def _render_entity_card(self, entity: pd.Series):

        """Render individual entity selection card."""

        is_active = entity['is_active']

        status_icon = "✅" if is_active else "⏸️"

        status_text = "Active Agent" if is_active else "Dormant"

        

        with st.container():

            st.markdown(f"**{status_icon} {entity['label']}**")

            st.markdown(f"*{entity['type']} • {status_text}*")

            

            # Selection button

            button_text = "Edit Agent" if is_active else "Activate"

            button_type = "secondary" if is_active else "primary"

            

            if st.button(button_text, key=f"select_{entity['id']}", type=button_type):

                self.session.selected_entity = {

                    'id': entity['id'],

                    'label': entity['label'],

                    'type': entity['type'],

                    'is_active': is_active,

                    'persona_prompt': entity.get('persona_prompt', ''),

                    'goals': entity.get('goals', '[]'),

                    'capabilities': entity.get('capabilities', '[]'),

                    'state': entity.get('state', '{}')

                }

                st.rerun()

            

            st.markdown("---")

    

    def _render_agent_editor(self):

        """Render the agent editing interface."""

        selected = self.session.selected_entity

        

        if not selected:

            st.info("👈 **Select an entity** to create or edit an agent")

            return

        

        st.subheader(f"🎭 Agent Editor: {selected['label']}")

        st.markdown(f"**Type:** {selected['type']} • **ID:** `{selected['id']}`")

        

        # Load entity details

        entity_details = self._get_entity_details(selected['id'])

        

        # Show entity context

        with st.expander("📄 Entity Context", expanded=False):

            if entity_details:

                st.markdown("**Original Entity Attributes:**")

                try:

                    attrs = json.loads(entity_details['attributes_json'])

                    for key, value in attrs.items():

                        st.markdown(f"• **{key}:** {value}")

                except:

                    st.markdown(entity_details['attributes_json'])

            else:

                st.markdown("*No additional context available*")

        

        # Agent configuration form

        with st.form(f"agent_form_{selected['id']}"):

            

            # Persona prompt

            st.markdown("### 🎯 Agent Persona")

            persona_prompt = st.text_area(

                "System Prompt",

                value=selected.get('persona_prompt', self._generate_default_prompt(selected)),

                height=200,

                help="This prompt defines the agent's personality, background, and behavior patterns. It will be sent to the LLM when this agent is active in simulations.",

                placeholder=f"You are {selected['label']}, a {selected['type'].lower()}..."

            )

            

            # Goals

            st.markdown("### 🎯 Agent Goals")

            goals_input = st.text_area(

                "Goals (JSON array)",

                value=selected.get('goals', '["Achieve primary objectives", "Maintain relationships"]'),

                height=100,

                help="Define what the agent wants to accomplish. Use JSON array format."

            )

            

            # Capabilities  

            st.markdown("### ⚡ Agent Capabilities")

            capabilities_input = st.text_area(

                "Capabilities (JSON array)", 

                value=selected.get('capabilities', '["Communication", "Decision making", "Information gathering"]'),

                height=100,

                help="Define what the agent can do. Use JSON array format."

            )

            

            # Initial state

            st.markdown("### 📊 Initial State")

            state_input = st.text_area(

                "Initial State (JSON object)",

                value=selected.get('state', '{"status": "ready", "location": "unknown", "resources": {}}'),

                height=100,

                help="Define the agent's starting conditions. Use JSON object format."

            )

            

            # Form buttons

            col1, col2, col3 = st.columns(3)

            

            with col1:

                save_clicked = st.form_submit_button("💾 Save Agent", type="primary")

            

            with col2:

                if selected['is_active']:

                    deactivate_clicked = st.form_submit_button("❌ Deactivate")

                else:

                    deactivate_clicked = False

            

            with col3:

                cancel_clicked = st.form_submit_button("🚫 Cancel")

        

        # Handle form submission

        if save_clicked:

            # Ensure all arguments are strings, not None

            persona_prompt = persona_prompt or ""

            goals_input = goals_input or "[]"

            capabilities_input = capabilities_input or "[]"

            state_input = state_input or "{}"

            self._save_agent(selected, persona_prompt, goals_input, capabilities_input, state_input)

        

        if deactivate_clicked:

            self._deactivate_agent(selected['id'])

        

        if cancel_clicked:

            self.session.selected_entity = None

            st.rerun()

    

    def _get_entity_details(self, entity_id: str) -> Dict[str, Any]:

        """Get detailed entity information."""

        if not self.session.db or not self.session.db.world_conn:

            return {}

        result = self.session.db.world_conn.execute("""

            SELECT id, type, label, attributes_json

            FROM raw_db.entities 

            WHERE id = ?

        """, [entity_id]).fetchone()

        

        if result:

            return {

                'id': result[0],

                'type': result[1],

                'label': result[2],

                'attributes_json': result[3]

            }

        return {}

    

    def _generate_default_prompt(self, entity: Dict[str, Any]) -> str:

        """Generate a default persona prompt for an entity."""

        label = entity['label']

        entity_type = entity['type'].lower()

        

        if entity_type == 'person':

            return f"""You are {label}, a person with unique experiences, knowledge, and perspectives.



Personality:

- You have your own motivations, fears, and desires

- You respond based on your background and expertise

- You maintain consistent behavior patterns



Communication Style:

- Speak in first person as {label}

- Draw from your personal experiences and knowledge

- Show emotional responses appropriate to situations



Goals:

- Pursue your personal and professional objectives

- Build and maintain relationships with others

- Respond authentically to changing circumstances"""



        elif entity_type == 'organization':

            return f"""You are a representative of {label}, speaking on behalf of the organization.



Organizational Identity:

- You represent the interests and values of {label}

- You have access to organizational resources and information

- You follow established policies and procedures



Communication Style:

- Speak with the authority of {label}

- Reference organizational goals and capabilities

- Maintain professional standards



Responsibilities:

- Advance the mission of {label}

- Coordinate with other entities as needed

- Protect organizational interests"""



        else:

            return f"""You are {label}, a {entity_type} with your own unique characteristics.



Identity:

- You have distinct traits and behaviors

- You operate according to your nature and purpose

- You interact meaningfully with your environment



Behavior:

- Act consistently with your established character

- Respond appropriately to different situations

- Maintain your core identity while adapting to circumstances



Purpose:

- Fulfill your role in the simulation world

- Contribute meaningfully to scenarios and interactions

- Develop and evolve based on experiences"""

    

    def _save_agent(self, entity: Dict[str, Any], persona: str, goals: str, capabilities: str, state: str):

        """Save agent configuration to the database."""

        if not self.session.db or not self.session.db.world_conn:

            st.error("No database connection.")

            return

        try:

            # Ensure no None values for required string arguments

            persona = persona or ""

            goals = goals or "[]"

            capabilities = capabilities or "[]"

            state = state or "{}"

            # Validate JSON inputs

            json.loads(goals)

            json.loads(capabilities)

            json.loads(state)

            # Save to database

            self.session.db.world_conn.execute("""

                INSERT INTO active_agents 

                    (agent_id, persona_prompt, goals, capabilities, state)

                VALUES (?, ?, ?, ?, ?)

                ON CONFLICT (agent_id) DO UPDATE SET

                    persona_prompt = excluded.persona_prompt,

                    goals = excluded.goals,

                    capabilities = excluded.capabilities,

                    state = excluded.state,

                    updated_at = now()

            """, [entity['id'], persona, goals, capabilities, state])

            self.session.db.world_conn.commit()

            st.success(f"✅ Agent '{entity['label']}' saved successfully!")

            # Clear selection

            self.session.selected_entity = None

            st.rerun()

        except json.JSONDecodeError as e:

            st.error(f"❌ Invalid JSON format: {e}")

        except Exception as e:

            st.error(f"❌ Error saving agent: {e}")

    

    def _deactivate_agent(self, agent_id: str):

        """Deactivate an agent by removing from active_agents table."""

        if not self.session.db or not self.session.db.world_conn:

            st.error("No database connection.")

            return

        try:

            self.session.db.world_conn.execute("""

                DELETE FROM active_agents WHERE agent_id = ?

            """, [agent_id])

            self.session.db.world_conn.commit()

            st.success("✅ Agent deactivated successfully!")

            # Clear selection

            self.session.selected_entity = None

            st.rerun()

        except Exception as e:

            st.error(f"❌ Error deactivating agent: {e}")



def render_agent_forge(session: Session):

    """Render function for the Agent Forge page."""

    page = AgentForgePage(session)

    page.render()